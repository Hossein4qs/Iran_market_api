"""منبع: alanchand.com  (صفحه‌ها سمت سرور رندر می‌شوند؛ فقط جدول HTML خوانده می‌شود)"""
import re
import sys

from .common import (FA_RE, NUM_RE, ascii_digits, cell_text, direction, link_slug,
                     norm, parse_table_page, signed, split_price_cell, to_number)
from .tags import currency_symbol, gold_symbol

ID = "alanchand"          # نام فایل خروجی: data/alanchand.json
NAME = "الان چند"
BASE = "https://alanchand.com"
PAGES = {                 # دسته -> (عنوان، مسیر صفحه)
    "currency": ("ارز", "/currencies-price"),
    "gold": ("طلا و سکه", "/gold-price"),
    "crypto": ("ارز دیجیتال", "/crypto-price"),
}
# حداقل تعداد ردیف‌های قابل‌قبول؛ کمتر از این یعنی ساختار صفحه عوض شده
MIN_ITEMS = {"currency": 10, "gold": 4, "crypto": 10}



# ---------- پارسرهای هر دسته (هر کدام یک <tr> می‌گیرند؛ ردیف نامربوط -> None) ----------
def parse_currency_row(row, cells):
    if len(cells) < 3:
        return None
    name = cell_text(cells[0])
    buy, sell = to_number(cell_text(cells[1])), to_number(cell_text(cells[2]))
    if not name or buy is None or sell is None:
        return None
    found = currency_symbol(name)
    if found:
        symbol, qty = found
    else:
        print(f"  ! ارز ناشناخته (نماد حدسی): {name}", file=sys.stderr)
        symbol, qty = norm(name), 1
    per_usd = to_number(cell_text(cells[3])) if len(cells) > 3 else None
    avg = (buy + sell) / 2
    return {"symbol": symbol, "name": name, "quantity": qty,
            "buy": buy, "sell": sell,
            "average": int(avg) if float(avg).is_integer() else avg,
            "per_usd": per_usd}


def parse_gold_row(row, cells):
    if len(cells) < 2:
        return None
    name = cell_text(cells[0])
    ptxt = cell_text(cells[1])
    price, pct, unit = split_price_cell(ptxt)
    if not name or price is None:
        return None
    d = direction(cells[1], ptxt, pct)
    # اول نماد مشترک (tags.py)، بعد slug لینک ردیف
    symbol = gold_symbol(name) or link_slug(row, "/gold-price")
    if not symbol:
        print(f"  ! آیتم طلای ناشناخته (نماد حدسی): {name}", file=sys.stderr)
        symbol = norm(name)
    real = bubble = bubble_pct = None
    if len(cells) > 2:
        real = to_number(cell_text(cells[2]))
    if len(cells) > 3:
        btxt = ascii_digits(cell_text(cells[3]))
        nums = NUM_RE.findall(btxt)
        if len(nums) >= 2:
            bubble, bubble_pct = to_number(nums[0]), to_number(nums[1])
    return {"symbol": symbol, "name": name, "price": price,
            "unit": unit or "toman", "change_percent": signed(pct, d),
            "change_percent_abs": pct, "real_price": real,
            "bubble": bubble, "bubble_percent": bubble_pct}


def parse_crypto_row(row, cells):
    if len(cells) < 3:
        return None
    img = cells[0].find("img", src=re.compile(r"/crypto/[^/]+\.\w+"))
    toman_txt, usd_txt = cell_text(cells[1]), cell_text(cells[2])
    p_toman, pct_toman, _ = split_price_cell(toman_txt)
    p_usd, pct_usd, _ = split_price_cell(usd_txt)
    if p_usd is None and p_toman is None:
        return None
    tokens = cell_text(cells[0]).split()
    fa, en = [], []
    for t in tokens:
        (en if (en or not FA_RE.search(t)) else fa).append(t)
    symbol = None
    if img:
        symbol = re.search(r"/crypto/([^/.]+)\.", img["src"]).group(1).upper()
    elif en:
        symbol = en[-1].upper()
    if not symbol:
        return None
    if en and en[-1].upper() == symbol:
        en = en[:-1]
    d_t, d_u = direction(cells[1], toman_txt, pct_toman), direction(cells[2], usd_txt, pct_usd)
    return {"symbol": symbol, "name": " ".join(fa) or None, "name_en": " ".join(en) or None,
            # قیمت تومانی ۰ یعنی بازار داخلی آن را پوشش نمی‌دهد
            "price_toman": p_toman or None,
            "change_percent_toman": signed(pct_toman, d_t), "change_percent_toman_abs": pct_toman,
            "price_usd": p_usd,
            "change_percent_usd": signed(pct_usd, d_u), "change_percent_usd_abs": pct_usd}


ROW_PARSERS = {"currency": parse_currency_row, "gold": parse_gold_row, "crypto": parse_crypto_row}


def parse_page(category, html):
    """-> (items, site_updated)"""
    return parse_table_page(html, ROW_PARSERS[category])
