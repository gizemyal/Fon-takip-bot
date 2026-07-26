import os
import sys
import subprocess
import re
from datetime import datetime, timedelta
import pytz

# Gerekli kütüphaneyi GitHub sunucusuna otomatik yüklüyoruz
def install_package(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])
    except Exception as e:
        print(f"Paket yükleme hatası ({package}): {e}")

try:
    import cloudscraper
except ImportError:
    install_package("cloudscraper")
    import cloudscraper

try:
    import requests
except ImportError:
    install_package("requests")
    import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FON_KODLARI = ["TLY", "PBR"]

def get_data_via_cloudscraper(fon_kodu):
    """Yöntem 1: TEFAS Cloudflare korumasını aşarak veriyi çeker"""
    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        
        # Oturum oluşturma
        scraper.get("https://www.tefas.gov.tr/TarihselVeriler.aspx", timeout=10)
        
        today = datetime.now()
        start_date = (today - timedelta(days=15)).strftime("%d.%m.%Y")
        end_date = today.strftime("%d.%m.%Y")
        
        payload = {
            "fontip": "YAT",
            "bastarih": start_date,
            "bittarih": end_date,
            "fonkod": fon_kodu
        }
        
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.tefas.gov.tr",
            "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx"
        }
        
        res = scraper.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo", data=payload, headers=headers, timeout=12)
        
        if res.status_code == 200:
            data = res.json().get("data", [])
            if data and len(data) >= 1:
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
        print(f"Cloudscraper Hatası ({fon_kodu}): {e}")
    return None, ""

def get_data_via_isyatirim(fon_kodu):
    """Yöntem 2: İş Yatırım yedek kaynağından fon verisini çeker"""
    try:
        url = f"https://www.isyatirim.com.tr/tr-tr/analiz/fon/Sayfalar/default.aspx"
        scraper = cloudscraper.create_scraper()
        res = scraper.get(f"https://www.isyatirim.com.tr/tr-tr/analiz/fon/Sayfalar/fon-detay.aspx?fonkod={fon_kodu}", timeout=10)
        
        if res.status_code == 200:
            # Fiyat arama
            price_match = re.search(r'Fiyat\s*\(TL\)[\s\S]*?<td>([\d,\.]+)</td>', res.text) or \
                          re.search(r'class="value"[^>]*>([\d,\.]+)<', res.text)
            if price_match:
                price = float(price_match.group(1).replace(",", ".").strip())
                return price, ""
    except Exception as e:
        print(f"İş Yatırım Hatası ({fon_kodu}): {e}")
    return None, ""

def get_fund_data(fon_kodu):
    # 1. Deneme: Cloudscraper ile TEFAS
    price, change = get_data_via_cloudscraper(fon_kodu)
    if price is not None:
        return price, change
        
    # 2. Deneme: İş Yatırım (Yedek)
    price, change = get_data_via_isyatirim(fon_kodu)
    if price is not None:
        return price, change

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
