<div align="center">

# 🌍 Global Price Search

### Tek arama. Dört ülke. Düzenli ürün verisi.

Türkçe ürün adını yaz; Amazon Türkiye, ABD, Japonya ve Almanya sonuçlarını JSON olarak topla.

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Browser-Playwright-2EAD33?style=for-the-badge)
![JSON](https://img.shields.io/badge/Output-JSON-F59E0B?style=for-the-badge&logo=json&logoColor=white)

**🇹🇷 Türkiye · 🇺🇸 ABD · 🇯🇵 Japonya · 🇩🇪 Almanya**

[Özellikler](#-neler-yapar) · [Kurulum](#-hızlı-kurulum) · [Kullanım](#-kullanım) · [JSON çıktısı](#-çıktıyı-tanı)

</div>

---

## ✨ Neler yapar?

- **Dört pazarda arama:** Tek komutla seçtiğin Amazon ülkelerini sırayla sorgular.
- **Otomatik çeviri:** Türkçe sorguyu İngilizce, Japonca ve Almancaya çevirir. Marka/model aramalarında kapatılabilir.
- **Ürünle eşleşen fiyat:** Ürün adı ve fiyatı aynı sonuç kartından alır; sayfalardaki tekrarları ASIN ile eler.
- **İşlenebilir çıktı:** Ürün adı, fiyat, ASIN ve bağlantıyı ülke bazında JSON dosyalarına kaydeder.
- **Görünür hata durumu:** CAPTCHA, HTTP hatası ve eksik fiyatları çıktıda belirtir; alınabilen sonuçları korur.

## 🗺️ Desteklenen pazarlar

| Pazar | Kod | Amazon adresi | Arama dili | Varsayılan para birimi |
| :--- | :---: | :--- | :--- | :---: |
| 🇹🇷 Türkiye | `tr` | amazon.com.tr | Türkçe | TRY |
| 🇺🇸 ABD | `us` | amazon.com | İngilizce | USD |
| 🇯🇵 Japonya | `jp` | amazon.co.jp | Japonca | JPY |
| 🇩🇪 Almanya | `de` | amazon.de | Almanca | EUR |

## 🚀 Hızlı kurulum

**Gereksinimler:** Python 3.10+, internet bağlantısı ve Playwright Chromium.

Proje klasöründe PowerShell açıp çalıştır:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m playwright install chromium
```

İlk aramanı başlat:

```powershell
.\venv\Scripts\python.exe main.py "kablosuz kulaklık" --countries tr --pages 1
```

<details>
<summary><strong>macOS / Linux komutları</strong></summary>

```bash
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
./venv/bin/python -m playwright install --with-deps chromium
./venv/bin/python main.py "kablosuz kulaklık" --countries tr --pages 1
```

Linux'ta tarayıcı sistem bağımlılıklarının kurulumu yönetici yetkisi gerektirebilir.

</details>

## 🔎 Kullanım

### Dört ülkede ara

```powershell
.\venv\Scripts\python.exe main.py "mekanik klavye"
```

Varsayılan olarak her ülkede **5 sayfa** aranır. Ülkeler sırayla sorgulanır ve sayfalar arasında **2 saniye** beklenir. Ürün adını komutta vermezsen program sana sorar.

### Ülkeleri ve sayfa sayısını seç

```powershell
.\venv\Scripts\python.exe main.py "oyuncu faresi" --countries tr de --pages 2
```

### Marka ve model adını çevirmeden ara

```powershell
.\venv\Scripts\python.exe main.py "Logitech MX Master" --no-translate --output-dir results
```

### Tarayıcı penceresini göster

```powershell
.\venv\Scripts\python.exe main.py "kulaklık" --countries tr --pages 1 --headed
```

| Seçenek | Ne yapar? | Varsayılan |
| :--- | :--- | :--- |
| `query` | Aranacak ürün adı; verilmezse sorulur | — |
| `--countries` | Bir veya daha fazla ülke: `tr us jp de` | Dört ülke |
| `--pages` | Ülke başına aranacak sayfa sayısı; en az 1 | `5` |
| `--output-dir` | JSON dosyalarının yazılacağı klasör | Çalışma dizini |
| `--headed` | Tarayıcı penceresini açar | Kapalı |
| `--no-translate` | Sorguyu tüm ülkelerde aynen kullanır | Çeviri açık |
| `--help` | Komut yardımını gösterir | — |

## 📦 Çıktıyı tanı

Her sorgulanan ülke için ayrı dosya oluşturulur:

```text
results/
├── amazon_tr.json
├── amazon_us.json
├── amazon_jp.json
└── amazon_de.json
```

Aşağıdaki veri, çıktı yapısını göstermek için hazırlanmış **temsili bir örnektir**:

```json
{
  "query": "kablosuz klavye",
  "search_term": "kablosuz klavye",
  "country": "tr",
  "currency": "TRY",
  "status": "ok",
  "errors": [],
  "warnings": [],
  "items": [
    {
      "asin": "EXAMPLE001",
      "name": "Örnek Kablosuz Klavye",
      "price": "749,90 TL",
      "url": "https://www.amazon.com.tr/dp/EXAMPLE001"
    }
  ],
  "products": ["Örnek Kablosuz Klavye"],
  "prices": ["749,90 TL"]
}
```

- `items`, ürün kayıtlarının tamamını içerir. Fiyat gösterilmiyorsa `price: null` yazılır.
- `products` ve `prices`, aynı sırayı koruyan yardımcı listelerdir.
- Aynı ülkenin dosyası sonraki aramada yenilenir. Eski aramaları saklamak için farklı bir `--output-dir` seç.

| Durum | Anlamı |
| :--- | :--- |
| `ok` | Ürünler alındı; sayfa hatası veya tüm fiyatların eksik olması durumu yok |
| `partial` | Bazı sayfalar alınamadı veya hiçbir ürünün fiyatı gösterilmedi |
| `error` | Arama hatası nedeniyle ürün alınamadı |

Birden fazla ülke aranırken bir ülkede sayfa hatası olması diğer ülke aramalarını durdurmaz. Herhangi bir sonuç `partial` veya `error` ise program **1** çıkış koduyla tamamlanır; tüm sonuçlar `ok` ise **0** döner.

## 🧭 Sonuçları yorumlarken

> Amazon'un gösterdiği veri; teslimat konumu, ürün seçenekleri ve erişim durumuna göre değişebilir.

Fiyatlar, sayfada görüldüğü biçimde metin olarak saklanır. Kur dönüşümü, kargo ve vergi hesabı yapılmaz. `currency`, pazarın varsayılan para birimidir; Amazon'un gösterdiği para birimi konum tercihlerine göre farklı olabilir. Bu nedenle çıktılar doğrudan toplam satın alma maliyeti olarak değerlendirilmemelidir.

Amazon CAPTCHA veya HTTP 503 gibi erişim engelleri gösterebilir. Program bunları raporlar; CAPTCHA çözmez. Sayfa yapısı değiştiğinde ürün seçicilerinin güncellenmesi gerekebilir. `ok` durumu, her ürünün fiyatının bulunduğu anlamına gelmez; fiyatı olmayan kayıtlar `null` olarak korunur.

Çeviri için sorgu MyMemory servisine HTTPS üzerinden gönderilir. İstek zaman aşımına uğrarsa veya servis hata verirse özgün ürün adıyla aramaya devam edilir.

## 🧪 Testler

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testler canlı Amazon bağlantısı kullanmadan şunları kontrol eder:

- Ürün–fiyat eşleşmesi, eksik fiyatlar ve tekrar eden kayıtlar.
- Tarayıcı üzerinden gezinme, sayfalama ve JSON kaydı.
- CAPTCHA, HTTP hatası ve kısmi sonuçların korunması.
- Çeviri hatasında özgün sorguya dönüş.
- JSON serileştirme hatasında önceki dosyanın korunması.

Tarayıcı testleri için Chromium kurulumu gereklidir.

## 🛠️ Proje yapısı

```text
global_price_search/
├── main.py             # Arama, çeviri, ayrıştırma ve JSON çıktısı
├── requirements.txt    # Python bağımlılıkları
├── tests/
│   └── test_main.py    # Birim ve tarayıcı entegrasyon testleri
├── .gitignore          # Sanal ortamları ve üretilen çıktıları dışlar
└── README.md
```

<div align="center">

**Python · Playwright · Beautiful Soup · Requests**

<sub>Ürünleri keşfet. Veriyi düzenli tut. Fiyatları bağlamıyla değerlendir.</sub>

</div>
