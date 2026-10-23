![last update](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FHossein4qs%2FIran_market_api%2Fmain%2Fdata%2Falanchand.json&query=%24.updated_at_tehran&label=last%20update&color=blue)

<div dir="rtl">

# Iran Market API

قیمت دلار، طلا، سکه و کریپتو به‌صورت JSON، رایگان و بدون نیاز به توکن یا ثبت‌نام.

یه اسکریپت پایتونی هر ۱۵ دقیقه قیمت‌ها رو از [الان‌چند](https://alanchand.com) و [ریال نرخ](https://rialnerkh.com) می‌خونه و توی همین ریپو ذخیره می‌کنه. تو هم می‌تونی مستقیم از GitHub بخونیش. سرور و دیتابیسی در کار نیست؛ همه‌چیز با GitHub Actions و GitHub Pages می‌چرخه.

🔗 **دمو:** https://hossein4qs.github.io/Iran_market_api/

## چرا ساختمش؟

وب‌سرویس‌های رسمی قیمت یا پولین یا محدودیت دارن (مثلاً نسخه‌ی رایگان الان‌چند فقط ساعتی یه درخواست می‌ده). من فقط یه JSON ساده می‌خواستم که بشه تو پروژه‌های کوچیک، ربات تلگرام یا یه اپ شخصی ازش استفاده کرد.

## استفاده

برای هر منبع یه فایل جدا داریم:

```
https://raw.githubusercontent.com/Hossein4qs/Iran_market_api/main/data/alanchand.json
https://raw.githubusercontent.com/Hossein4qs/Iran_market_api/main/data/rialnerkh.json
```

مثلاً قیمت دلار با جاوااسکریپت:

```js
const url = "https://raw.githubusercontent.com/Hossein4qs/Iran_market_api/main/data/alanchand.json";
const data = await (await fetch(url)).json();

const usd = data.categories.currency.items.find(i => i.tag === "currency:usd");
console.log(usd.price); // قیمت به تومان
```

یادتون باشه `raw.githubusercontent.com` خودش چند دقیقه کش می‌کنه، پس ممکنه آخرین آپدیت با کمی تأخیر برسه.

## خروجی چه شکلیه؟

هر فایل یه منبع داره و قیمت‌ها توی چهار دسته‌ان: `currency` (ارز)، `gold` (طلا و سکه)، `crypto` و `official` (نرخ رسمی، فقط ریال نرخ).

```json
{
  "source": { "id": "alanchand", "name": "الان چند", "url": "https://alanchand.com" },
  "updated_at_utc": "...",
  "updated_at_tehran": "...",
  "categories": {
    "currency": {
      "title": "ارز",
      "items": [
        { "tag": "currency:usd", "name": "دلار آمریکا", "buy": 0, "sell": 0, "price": 0 }
      ]
    }
  }
}
```

چند نکته که خوبه بدونید:

- **همه‌ی قیمت‌ها تومانن**، مگه اینکه `unit: "usd"` داشته باشن (مثل انس طلا).
- **`price` همیشه قیمت اصلیه.** اگه منبع خرید و فروش جدا بده، `price` میانگینشونه.
- **هر آیتم یه `tag` داره** مثل `currency:usd` یا `gold:sekkeh` یا `crypto:btc`. این تگ توی همه‌ی منابع یکسانه، پس برای مقایسه‌ی دو منبع فقط کافیه آیتم‌ها رو با `tag` بهم وصل کنی.
- ارزهایی که منبع «صدتایی» می‌ده (مثل صد ین) بر ۱۰۰ تقسیم می‌شن؛ `quantity` همیشه ۱ه.
- `change_percent` فقط وقتی پر می‌شه که جهت تغییر (بالا یا پایین) از صفحه معلوم باشه، وگرنه `null` می‌مونه و عدد خام توی `change_percent_abs` هست.
- اگه یه دسته توی اجرای آخر خونده نشه، داده‌ی قبلیش می‌مونه و `"stale": true` و یه فیلد `error` می‌گیره.
- اگه همه‌ی دسته‌های یه منبع خراب بشن، فایل اون منبع دست نمی‌خوره و workflow قرمز می‌شه.

### فرق دو منبع

| | الان چند | ریال نرخ |
|---|---|---|
| ارز | `buy`، `sell` و `price` | فقط `price` |
| طلا | `price`، `change_percent`، `bubble_percent` | `price`، `change`، `change_percent`، `bubble` |
| کریپتو | `price` (تومان) و `price_usd` | فقط `price` (تومان) |
| نرخ رسمی | ندارد | دسته‌ی `official` |

## راه‌اندازی روی ریپوی خودت

1. ریپو رو فورک کن یا کدش رو توی یه ریپوی جدید بریز.
2. از Settings ← Actions ← General گزینه‌ی **Read and write permissions** رو فعال کن.
3. از تب Actions، workflow با اسم *Update prices* رو یه بار دستی اجرا کن. از اون به بعد خودش هر ۱۵ دقیقه اجرا می‌شه.

## اجرای لوکال

```bash
pip install -r requirements.txt
python scraper.py
```

خروجی توی پوشه‌ی `data/` ساخته می‌شه.

## افزودن منبع جدید

1. توی `sources/` یه فایل بساز، مثلاً `sources/mysite.py`، شبیه `sources/alanchand.py`. لازمه این‌ها رو داشته باشه: `ID`، `NAME`، `BASE`، `PAGES`، `MIN_ITEMS` و تابع `parse_page(category, html)` که `(items, site_updated)` برمی‌گردونه.
2. نمادها رو با `currency_symbol()` و `gold_symbol()` از `sources/tags.py` بگیر تا تگ‌ها با بقیه‌ی منابع یکی بشه. اگه ارز یا کالایی اونجا نبود، یه خط به دیکشنری اضافه کن. برای رمزارز، نماد همون تیکره (`BTC` می‌شه `crypto:btc`).
3. ماژول رو به `SOURCES` توی `sources/__init__.py` و `id` ش رو به `SOURCE_IDS` توی `index.html` اضافه کن.

نیازی نیست `tag` رو خودت بسازی؛ `scraper.py` از روی دسته و نماد می‌سازه. دریافت صفحه، تلاش مجدد، `stale` و ذخیره‌ی HTML خراب برای همه‌ی منابع مشترکه.

## وقتی چیزی خراب شد

سایت‌ها هر وقت بخوان ظاهرشون رو عوض می‌کنن و اون موقع پارسر می‌ترکه. در این حالت workflow شکست می‌خوره و HTML صفحه‌ی خراب به‌صورت artifact با اسم `debug-html` ذخیره می‌شه تا بتونی ببینی چی عوض شده. پارسر هر منبع توی `sources/` هست (مثلاً توابع `parse_*_row` توی `sources/alanchand.py`).

اگه الان‌چند ارز جدیدی اضافه کنه، توی لاگ هشدار «ارز ناشناخته» می‌بینی و فقط باید یه خط به `CURRENCIES` یا `GOLD` توی `sources/tags.py` اضافه کنی.

## چند نکته‌ی مهم

- زمان‌بندی GitHub Actions دقیق نیست و ممکنه چند دقیقه دیر بشه.
- این پروژه داده‌ها رو از سایت‌های دیگه می‌خونه. قبل از استفاده‌ی عمومی یا تجاری، شرایط استفاده‌ی هر سایت رو چک کن.
- صفحه‌ی قوانین **ریال نرخ** اسکرپ رو صریحاً ممنوع نکرده، ولی بازنشر بخش قابل‌توجهی از سایت بدون اجازه‌ی کتبی رو مجاز نمی‌دونه. اگه ریپو عمومیه و `data/rialnerkh.json` منتشر می‌شه، بهتره از سایت اجازه بگیری.
- الان‌چند یه [وب‌سرویس رسمی](https://alanchand.com/media/api) هم داره که با توکن کار می‌کنه. اگه پروژه‌ات جدیه، اون گزینه‌ی مطمئن‌تریه.
- قیمت‌ها فقط برای اطلاعاته؛ برای معامله‌ی واقعی بهشون تکیه نکن.

## مشارکت

Issue و PR خوشحالم می‌کنه، مخصوصاً برای منبع‌های جدید یا نمادهای جاافتاده.

</div>
