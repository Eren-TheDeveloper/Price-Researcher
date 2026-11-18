"""Amazon'un dört ülke sitesinde ürün arar ve sonuçları JSON'a kaydeder."""

import argparse
import asyncio
import json
from html import unescape
from pathlib import Path
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup
import requests
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

MARKETS = {
    'tr': ('https://www.amazon.com.tr', 'tr', 'TRY'),
    'us': ('https://www.amazon.com', 'en', 'USD'),
    'jp': ('https://www.amazon.co.jp', 'ja', 'JPY'),
    'de': ('https://www.amazon.de', 'de', 'EUR'),
}
RESULT_SELECTOR = '[data-component-type="s-search-result"][data-asin]'


def parse_products(html, base_url):
    """Başlık ve fiyatı aynı karttan alır; fiyatı olmayan ürünü korur."""
    soup = BeautifulSoup(html, 'html.parser')
    items, seen = [], set()
    for card in soup.select(RESULT_SELECTOR):
        asin = card.get('data-asin', '').strip()
        title = card.select_one('h2')
        if not asin or asin in seen or title is None:
            continue
        name = title.get_text(' ', strip=True)
        if not name:
            continue
        price_node = card.select_one('.a-price:not(.a-text-price) .a-offscreen')
        price = price_node.get_text(strip=True) if price_node else None
        if not price:
            whole = card.select_one('.a-price:not(.a-text-price) .a-price-whole')
            fraction = card.select_one('.a-price:not(.a-text-price) .a-price-fraction')
            if whole:
                price = whole.get_text(strip=True)
                if fraction:
                    if not price.endswith(('.', ',')):
                        price += '.'
                    price += fraction.get_text(strip=True)
        link = title.find_parent('a', href=True) or title.select_one('a[href]')
        items.append({
            'asin': asin, 'name': name, 'price': price,
            'url': urljoin(base_url, link['href'] if link else f'/dp/{asin}'),
        })
        seen.add(asin)
    return items


def is_blocked(html):
    soup = BeautifulSoup(html, 'html.parser')
    return bool(soup.select_one(
        'form[action*="validateCaptcha"], input#captchacharacters, '
        'img[src*="captcha"], form[action*="/errors/validate"]'
    )) or 'robot check' in (soup.title.get_text().lower() if soup.title else '')


def write_results(path, result):
    """Serileştirme başarısız olursa önceki çıktıyı bozmadan kaydeder."""
    content = json.dumps(result, ensure_ascii=False, indent=4)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(content + '\n', encoding='utf-8')
    temporary.replace(path)


def fetch_translation(query, language):
    response = requests.get(
        'https://api.mymemory.translated.net/get',
        params={'q': query, 'langpair': f'tr|{language}'},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if str(data.get('responseStatus')) != '200':
        raise ValueError(data.get('responseDetails') or 'Çeviri servisi hata verdi.')
    translated = data.get('responseData', {}).get('translatedText')
    if not isinstance(translated, str) or not translated.strip():
        raise ValueError('Çeviri servisi boş yanıt verdi.')
    return unescape(translated.strip())


async def translate_query(query, language, enabled):
    if not enabled or language == 'tr':
        return query
    try:
        return await asyncio.to_thread(fetch_translation, query, language)
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        print(f'Çeviri alınamadı ({language}); özgün sorgu kullanılacak: {exc}')
        return query


async def search_market(browser, country, query, pages, output_dir, translate=True, delay=2):
    base_url, language, currency = MARKETS[country]
    search_term = await translate_query(query, language, translate)
    items, errors, seen = [], [], set()
    context = await browser.new_context(locale={'tr': 'tr-TR', 'us': 'en-US', 'jp': 'ja-JP', 'de': 'de-DE'}[country])
    try:
        page = await context.new_page()
        for number in range(1, pages + 1):
            url = f"{base_url}/s?{urlencode({'k': search_term, 'page': number})}"
            try:
                response = await page.goto(url, wait_until='domcontentloaded', timeout=45000)
                if response is not None and response.status >= 400:
                    raise RuntimeError(f'HTTP {response.status}; Amazon isteği karşılamadı.')
                try:
                    await page.wait_for_selector(RESULT_SELECTOR, state='attached', timeout=10000)
                except PlaywrightTimeout:
                    pass
                html = await page.content()
                if is_blocked(html):
                    raise RuntimeError('Amazon CAPTCHA/robot doğrulaması gösterdi.')
                found = parse_products(html, base_url)
                if not found:
                    raise RuntimeError('Ürün kartı bulunamadı; sonuç yok, erişim engellendi veya sayfa yapısı değişti.')
                for item in found:
                    if item['asin'] not in seen:
                        seen.add(item['asin'])
                        items.append(item)
                print(f'[{country.upper()}] Sayfa {number}: {len(found)} ürün; toplam {len(items)}')
                if number < pages:
                    await asyncio.sleep(delay)
            except (PlaywrightError, RuntimeError) as exc:
                errors.append(f'Sayfa {number}: {exc}')
                print(f'[{country.upper()}] {errors[-1]}')
                break
    finally:
        await context.close()
    warnings = []
    if items and not any(item['price'] for item in items):
        warnings.append('Amazon ürünleri gösterdi ancak hiçbir fiyat gösterilmedi. Teslimat konumu veya ürün seçenekleri gerekebilir.')
        print(f'[{country.upper()}] {warnings[0]}')
    result = {
        'query': query, 'search_term': search_term, 'country': country,
        'currency': currency,
        'status': 'partial' if items and (errors or warnings) else 'error' if errors else 'ok',
        'errors': errors, 'warnings': warnings, 'items': items,
        'products': [item['name'] for item in items],
        'prices': [item['price'] for item in items],
    }
    path = Path(output_dir) / f'amazon_{country}.json'
    write_results(path, result)
    print(f'[{country.upper()}] Kaydedildi: {path}')
    return result


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('En az 1 olmalı.')
    return number


async def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', nargs='?', help='Türkçe ürün adı')
    parser.add_argument('--countries', nargs='+', choices=MARKETS, default=list(MARKETS))
    parser.add_argument('--pages', type=positive_int, default=5)
    parser.add_argument('--output-dir', type=Path, default=Path('.'))
    parser.add_argument('--headed', action='store_true', help='Tarayıcı penceresini göster')
    parser.add_argument('--no-translate', action='store_true', help='Tüm ülkelerde sorguyu aynen kullan')
    args = parser.parse_args(argv)
    query = (args.query if args.query is not None else input('Aramak istediğiniz ürünü yazınız: ')).strip()
    if not query:
        parser.error('Ürün adı boş olamaz.')
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not args.headed)
        try:
            results = []
            for country in dict.fromkeys(args.countries):
                results.append(await search_market(
                    browser, country, query, args.pages, args.output_dir,
                    translate=not args.no_translate,
                ))
        finally:
            await browser.close()
    return 1 if any(result['status'] != 'ok' for result in results) else 0


if __name__ == '__main__':
    try:
        raise SystemExit(asyncio.run(main()))
    except (PlaywrightError, OSError) as exc:
        print(f'Çalıştırma hatası: {exc}')
        print('Kurulum: python -m pip install -r requirements.txt; python -m playwright install chromium')
        raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        print('İşlem iptal edildi.')
        raise SystemExit(130)
