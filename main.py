import os
import json
import re
import requests
from datetime import datetime
import pytz

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FON_KODLARI = ["TLY", "PBR"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8"
}

def get_from_fintables(fon_kodu):
    """1. Kaynak: Fintables"""
    url = f"https://fintables.com/fonlar/{fon_kodu.upper()}"
    res = requests.get(url, headers=HEADERS, timeout=10)
    if res.status_code == 200:
        price_match = re.search(r'"price"\s*:\s*([\d\.]+)', res.text) or \
                      re.search(r'"last_price"\s*:\s*([\d\.]+)', res.text)
        change_match = re.search(r'"daily_return"\s*:\s*([-\d\.]+)', res.text) or \
                       re.search(r'"day_change"\s*:\s*([-\d\.]+)', res.text)
        
        if price_match:
            price = float(price_match.group(1))
            change_str = ""
            if change_match:
                change = float(change_match.group(1))
                emoji = "🟢" if change >= 0 else "🔴"
                sign = "+" if change >= 0 else ""
                change_str = f" ({sign}%{change:.2f} {emoji})"
            return price, change_str
    return None, ""

def get_from_mynet(fon_kodu):
    """2. Kaynak: Mynet Finans"""
    url = f"https://finans.mynet.com/fon/{fon_kodu.upper()}/"
    res = requests.get(url, headers=HEADERS, timeout=10)
    if res.status_code == 200:
        price_match = re.search(r'class="[^\"]*fiyat[^\"]*"[^>]*>([\d,\.]+)<', res.text, re.IGNORECASE) or \
                      re.search(r'([\d,\.]+)\s*TL', res.text)
        if price_match:
            price = float(price_match.group(1).replace(",", "."))
            return price, ""
    return None, ""

def get_from_doviz_com(fon_kodu):
    """3. Kaynak: Doviz.com"""
    url = f"https://fon.doviz.com/yatirim-fonlari/{fon_kodu.upper()}"
    res = requests.get(url, headers=HEADERS, timeout=10)
    if res.status_code == 200:
        price_match = re.search(r'class="value"[^>]*>([\d,\.]+)<', res.text) or \
                      re.search(r'data-socket-key="[^"]*"[^>]*>([\d,\.]+)<', res.text)
        if price_match:
            price = float(price_match.group(1).replace(",", "."))
            return price, ""
    return None, ""

def get_fund_data(fon_kodu):
    # 1. Deneme: Fintables
    try:
        price, change = get_from_fintables(fon_kodu)
        if price is not None:
            return price, change
    except Exception as e:
        print(f"Fintables hatası ({fon_kodu}): {e}")

    # 2. Deneme: Mynet
    try:
        price, change = get_from_mynet(fon_kodu)
        if price is not None:
            return price, change
    except Exception as e:
        print(f"Mynet hatası ({fon_kodu}): {e}")

    # 3. Deneme: Doviz.com
    try:
        price, change = get_from_doviz_com(fon_kodu)
        if price is not None:
            return price, change
    except Exception as e:
        print(f"Doviz.com hatası ({fon_kodu}): {e}")

    return None, ""

def send_telegram_message(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Bot Token veya Chat ID eksik!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def main():
    tr_tz = pytz.timezone("Europe/Istanbul")
    now_str = datetime.now(tr_tz).strftime("%d.%m.%Y | %H:%M")

    lines = [
        f"📅 *{now_str}*",
        "",
        "📊 *Günlük Fon Takibi*",
        ""
    ]

    icons = {"TLY": "🟦", "PBR": "🟩"}

    for kod in FON_KODLARI:
        price, change = get_fund_data(kod)
        icon = icons.get(kod, "🔹")
        if price is not None:
            lines.append(f"{icon} *{kod}:* {price:.4f} TL{change}")
        else:
            lines.append(f"{icon} *{kod}:* Veri alınamadı")

    msg = "\n".join(lines)
    send_telegram_message(msg)

if __name__ == "__main__":
    main()
