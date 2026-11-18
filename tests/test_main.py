import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import requests
from playwright.async_api import async_playwright

from main import fetch_translation, is_blocked, parse_products, search_market, translate_query, write_results

HTML = '''<html><body>
<span class="a-color-base">Sponsorlu 4,8</span>
<div data-component-type="s-search-result" data-asin="A1">
<a href="/dp/A1"><h2>Kablosuz <span>klavye</span></h2></a>
<span class="a-price a-text-price"><span class="a-offscreen">999 TL</span></span>
<span class="a-price"><span class="a-offscreen">749,90 TL</span></span></div>
<div data-component-type="s-search-result" data-asin="A2"><h2>Fiyatsız ürün</h2></div>
<div data-component-type="s-search-result" data-asin="A3"><h2>Mouse</h2>
<span class="a-price"><span class="a-price-whole">123,</span><span class="a-price-fraction">45</span></span></div>
<div data-component-type="s-search-result" data-asin="A1"><h2>Tekrar</h2></div>
<div data-component-type="s-search-result" data-asin=""><h2>Reklam</h2></div>
</body></html>'''


class ParsingTests(unittest.TestCase):
    def test_prices_stay_with_their_products(self):
        items = parse_products(HTML, 'https://www.amazon.com.tr')
        self.assertEqual([i['asin'] for i in items], ['A1', 'A2', 'A3'])
        self.assertEqual([i['price'] for i in items], ['749,90 TL', None, '123,45'])
        self.assertEqual(items[0]['name'], 'Kablosuz klavye')
        self.assertEqual(items[0]['url'], 'https://www.amazon.com.tr/dp/A1')
        self.assertEqual(items[1]['url'], 'https://www.amazon.com.tr/dp/A2')

    def test_captcha(self):
        self.assertTrue(is_blocked('<form action="/errors/validateCaptcha"></form>'))
        self.assertTrue(is_blocked('<title>Robot Check</title>'))
        self.assertFalse(is_blocked(HTML))

    def test_failed_serialization_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'amazon_tr.json'
            write_results(path, {'items': ['Türkçe']})
            with self.assertRaises(TypeError):
                write_results(path, {'items': [object()]})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'items': ['Türkçe']})

    @patch('main.requests.get')
    def test_translation_response_and_timeout(self, get):
        get.return_value.json.return_value = {'responseStatus': 200, 'responseData': {'translatedText': 'keyboard &amp; mouse'}}
        self.assertEqual(fetch_translation('klavye', 'en'), 'keyboard & mouse')
        self.assertEqual(get.call_args.kwargs['timeout'], 15)
        get.return_value.json.return_value = {'responseStatus': 429, 'responseDetails': 'Quota'}
        with self.assertRaisesRegex(ValueError, 'Quota'):
            fetch_translation('klavye', 'en')


class TranslationTests(unittest.IsolatedAsyncioTestCase):
    @patch('main.fetch_translation', side_effect=requests.Timeout('timeout'))
    async def test_translation_failure_uses_original_query(self, fetch):
        self.assertEqual(await translate_query('klavye', 'en', True), 'klavye')

    @patch('main.fetch_translation')
    async def test_translation_can_be_disabled(self, fetch):
        self.assertEqual(await translate_query('model X', 'en', False), 'model X')
        self.assertEqual(await translate_query('klavye', 'tr', True), 'klavye')
        fetch.assert_not_called()


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch()
        self.directory = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self.pw.stop)
        self.addAsyncCleanup(self.browser.close)
        self.addCleanup(self.directory.cleanup)

    async def test_navigation_pagination_and_json(self):
        urls = []
        async def serve(route):
            urls.append(route.request.url)
            await route.fulfill(status=200, content_type='text/html', body=HTML)
        await self._route_browser(serve)
        result = await search_market(self.browser, 'tr', 'klavye & mouse', 2, self.directory.name, translate=False, delay=0)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['items']), 3)
        self.assertEqual(result['prices'], ['749,90 TL', None, '123,45'])
        self.assertEqual(len(urls), 2)
        self.assertEqual(parse_qs(urlparse(urls[0]).query)['k'], ['klavye & mouse'])
        path = Path(self.directory.name) / 'amazon_tr.json'
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), result)
        self.assertEqual(len(self.browser.contexts), 0)

    async def _route_browser(self, handler):
        original = self.browser.new_context
        async def context_with_route(**kwargs):
            context = await original(**kwargs)
            await context.route('**/*', handler)
            return context
        self.browser.new_context = context_with_route

    async def test_http_error_keeps_partial_results(self):
        async def serve(route):
            second = parse_qs(urlparse(route.request.url).query)['page'] == ['2']
            await route.fulfill(status=503 if second else 200, content_type='text/html', body=HTML)
        await self._route_browser(serve)
        result = await search_market(self.browser, 'tr', 'klavye', 2, self.directory.name, translate=False, delay=0)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['items']), 3)
        self.assertIn('HTTP 503', result['errors'][0])

    async def test_captcha_is_reported_as_error(self):
        async def serve(route):
            await route.fulfill(status=200, content_type='text/html', body=HTML + '<input id="captchacharacters">')
        await self._route_browser(serve)
        result = await search_market(self.browser, 'tr', 'klavye', 1, self.directory.name, translate=False)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['items'], [])
        self.assertIn('CAPTCHA', result['errors'][0])

    async def test_missing_all_prices_is_reported_as_partial(self):
        async def serve(route):
            await route.fulfill(status=200, content_type='text/html', body=(
                '<div data-component-type="s-search-result" data-asin="A1">'
                '<h2>Ürün</h2></div>'
            ))
        await self._route_browser(serve)
        result = await search_market(self.browser, 'de', 'klavye', 1, self.directory.name, translate=False)
        self.assertEqual(result['status'], 'partial')
        self.assertIsNone(result['prices'][0])
        self.assertTrue(result['warnings'])


if __name__ == '__main__':
    unittest.main()
