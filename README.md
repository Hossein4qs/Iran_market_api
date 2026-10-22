# alanchand-prices

استخراج خودکار قیمت ارز، طلا، سکه و کریپتو از [alanchand.com](https://alanchand.com) و ذخیره در `data/prices.json`. هر ۱۵ دقیقه با GitHub Actions به‌روز می‌شود.

صفحه‌های الان‌چند سمت سرور رندر می‌شوند، پس اسکریپت فقط با `requests` و `BeautifulSoup` جدول‌های HTML را می‌خواند (بدون مرورگر).

## راه‌اندازی
1. این پوشه را در یک ریپوی جدید گیت‌هاب push کنید.
2. در Settings → Actions → General گزینه‌ی **Read and write permissions** را فعال کنید.
3. از تب Actions، workflow با نام *Update prices* را یک بار دستی اجرا کنید.

## دسترسی به JSON
```
https://raw.githubusercontent.com/<USER>/<REPO>/main/data/prices.json
```

## ساختار خروجی
```jsonc
{
  "source": "https://alanchand.com",
  "updated_at_utc": "...", "updated_at_tehran": "...",
  "categories": {
    "currency": { "title": "ارز", "site_updated": "…", "items": [
      { "symbol": "usd", "name": "دلار آمریکا", "quantity": 1, "buy": 267100, "sell": 269800, "per_usd": null } ] },
    "gold": { "items": [
      { "symbol": "sekkeh", "name": "سکه امامی (طرح جدید)", "price": 274000000, "unit": "toman",
        "change_percent": 0.5, "change_percent_abs": 0.5, "real_price": 259238000, "bubble": 9762000, "bubble_percent": 3.77 } ] },
    "crypto": { "items": [
      { "symbol": "BTC", "name": "بیت کوین", "name_en": "Bitcoin", "price_toman": 22179111200, "price_usd": 81940,
        "change_percent_toman": 0.64, "change_percent_toman_abs": 0.64, "change_percent_usd": 1.69, "change_percent_usd_abs": 1.69 } ] }
  }
}
```
- قیمت‌ها به **تومان** هستند، مگر `unit: "usd"` (مثلاً انس طلا).
- `quantity: 100` یعنی قیمت برای ۱۰۰ واحد است (مثل «صد ین»).
- `change_percent` فقط وقتی علامت‌دار پر می‌شود که جهت تغییر (بالا/پایین) از صفحه قابل تشخیص باشد؛ وگرنه `null` است و مقدار خام در `change_percent_abs` می‌ماند.
- `price_toman: null` برای رمزارزهایی است که الان‌چند برایشان قیمت تومانی ندارد (در سایت ۰ نمایش داده می‌شود).
- اگر یک دسته در اجرای آخر خوانده نشود، داده‌ی قبلی‌اش نگه داشته می‌شود و `"stale": true` و `"error"` می‌گیرد.
- هر دسته `site_updated` دارد (زمان به‌روزرسانی طبق خود سایت)؛ صفحه‌های سایت کش جداگانه دارند و ممکن است زمان‌شان با هم فرق کند.

## اجرای محلی
```
pip install -r requirements.txt
python scraper.py
```

## نکات
- اگر ساختار سایت عوض شد، اجرای workflow شکست می‌خورد و HTML خام صفحه‌ی خراب به‌صورت artifact با نام `debug-html` ذخیره می‌شود. پارسرها در `scraper.py` (توابع `parse_*_row`) هستند.
- نماد ارزها از روی نام فارسی نگاشت می‌شود (`CURRENCIES` و `GOLD` در بالای فایل)؛ اگر الان‌چند ارز جدیدی اضافه کند، هشدار «ارز ناشناخته» در لاگ می‌بینید و فقط باید یک خط به دیکشنری اضافه کنید.
- الان‌چند وب‌سرویس رسمی هم دارد ([alanchand.com/media/api](https://alanchand.com/media/api)) که با توکن کار می‌کند و نسخه‌ی رایگان آن محدود به یک درخواست در ساعت است. قبل از استفاده‌ی عمومی از داده‌ها، شرایط استفاده‌ی سایت را بررسی کنید.
- زمان‌بندی GitHub Actions دقیق نیست و ممکن است چند دقیقه تأخیر داشته باشد.
