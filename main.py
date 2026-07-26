import os
import requests
from datetime import datetime, timedelta
import pytz

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FON_KODLARI = ["TLY", "PBR"]

def get_fund_data(fon_kodu):
    url = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
    today = datetime.now()
    start_date = (today - timedelta(days=7)).strftime("%d.%m.%Y")
    end_date = today.strftime("%d.%m.%Y")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.tefas.gov.tr",
        "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx"
    }

    payload = {
        "fontip": "YAT",
        "bastarih": start_date,
        "bittarih": end_date,
        "fonkod": fon_kodu
    }

    try:
        res = requests.post(url, data=payload, headers=headers, timeout=10)
        data = res.json().get("data", [])
        if len(data) >= 1:
            latest = data[0]
            price = float(latest.get("BirimFiyat", 0))
            change_str = ""
            
            if len(data) >= 2:
                prev_price = float(data[1].get("BirimFiyat", 0))
                if prev_price > 0:
                    change = ((price - prev_price) / prev_price) * 100
                    emoji = "🟢" if change >= 0 else "🔴"
                    sign = "+" if change >= 0 else ""
                    change_str = f" ({sign}%{change:.2f} {emoji})"
                    
            return price, change_str
    except Exception as e:
        print(f"Hata ({fon_kodu}): {e}")
    return None, ""

def send_telegram_message(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Bot Token veya Chat ID bulunamadı!")
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
