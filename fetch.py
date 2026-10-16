"""Fetch current prices from TGJU and update latest.json + per-item daily OHLC history."""
import json, time, pathlib, datetime as dt
from zoneinfo import ZoneInfo
import requests

# اسم‌گذاری خودمون -> کلید TGJU (در صورت تغییر سایت اینجا اصلاح کن)
ITEMS = {
    "dollar":  {"fa": "دلار",        "key": "price_dollar_rl"},
    "euro":    {"fa": "یورو",        "key": "price_eur"},
    "gold18":  {"fa": "طلا ۱۸ عیار", "key": "geram18"},
    "coin":    {"fa": "سکه امامی",   "key": "sekee"},
    "ons":     {"fa": "اونس طلا",    "key": "ons"},
}
SOURCES = [
    "https://call5.tgju.org/ajax.json",
    "https://call4.tgju.org/ajax.json",
    "https://call3.tgju.org/ajax.json",
]
DATA = pathlib.Path("data"); HIST = DATA / "history"
HIST.mkdir(parents=True, exist_ok=True)

def get_current():
    last = None
    for url in SOURCES:
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            cur = r.json().get("current")
            if cur: return cur
        except Exception as e:
            last = e
    raise SystemExit(f"all sources failed: {last}")

def num(s):
    try: return float(str(s).replace(",", "").strip())
    except Exception: return None

cur = get_current()
now = dt.datetime.now(ZoneInfo("Asia/Tehran"))
today = now.date().isoformat()
latest = {"updated": now.isoformat(timespec="seconds"), "items": {}}

for name, meta in ITEMS.items():
    row = cur.get(meta["key"])
    if not row: continue
    p = num(row.get("p"))
    if p is None: continue
    latest["items"][name] = {"fa": meta["fa"], "price": p,
                             "change": num(row.get("d")), "percent": row.get("dp")}
    f = HIST / f"{name}.json"
    hist = json.loads(f.read_text()) if f.exists() else []
    if hist and hist[-1]["date"] == today:
        d = hist[-1]; d["high"] = max(d["high"], p); d["low"] = min(d["low"], p); d["close"] = p
    else:
        hist.append({"date": today, "open": p, "high": p, "low": p, "close": p})
    f.write_text(json.dumps(hist[-3650:], ensure_ascii=False, separators=(",", ":")))

(DATA / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2))
print("ok", list(latest["items"]))
