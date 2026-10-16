# chande-prices

استخراج خودکار قیمت ارز، طلا، سکه، کریپتو و کالا از [chande.net](https://chande.net) و ذخیره در `data/prices.json`. هر ۱۵ دقیقه با GitHub Actions به‌روز می‌شود.

## راه‌اندازی
1. این پوشه را در یک ریپوی جدید گیت‌هاب push کنید.
2. در Settings → Actions → General گزینه‌ی **Read and write permissions** را فعال کنید.
3. از تب Actions، workflow با نام *Update prices* را یک بار دستی اجرا کنید.

## دسترسی به JSON
```
https://raw.githubusercontent.com/<USER>/<REPO>/main/data/prices.json
```

## اجرای محلی
```
pip install -r requirements.txt
playwright install chromium
python scraper.py
```

## نکات
- اگر ساختار سایت عوض شد، فایل‌های `data/raw/*.json` (پاسخ‌های API خود سایت) برای اصلاح اسکریپت کمک می‌کنند.
- زمان‌بندی GitHub Actions دقیق نیست و ممکن است چند دقیقه تأخیر داشته باشد.
- قبل از استفاده‌ی عمومی، شرایط استفاده‌ی سایت مبدأ را بررسی کنید.
