import os
import ssl
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import urllib3
from datetime import datetime, timedelta
import pytz
import re

# SSL uyarılarını kapatıyoruz
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FON_KODLARI = ["TLY", "PBR"]

class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

def get_fund_data(fon_kodu):
    session = requests.Session()
    session.mount('https://', LegacySSLAdapter())
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    }
    session.headers.update(headers)

    # --- YÖNTEM 1: TEFAS API (Çerez Oturumu ile) ---
    try:
        # 1. Adım: ASP.NET Session Cookie almak için TarihselVeriler sayfasını ziyaret et
        session.get("https://www.tefas.gov.tr/TarihselVeriler.aspx", timeout=10, verify=False)
        
        today = datetime.now()
        start_date = (today - timedelta(days=15)).strftime("%d.%m.%Y")
        end_date = today.strftime("%d.%m.%Y")
        
        payload = {
            "fontip": "YAT",
            "bastarih": start_date,
            "bittarih": end_date,
            "fonkod": fon_kodu
        }
        
        api_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.tefas.gov.tr",
            "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx"
        }
        
        res = session.post("https://www.tefas.gov.tr/api/DB/BindHistoryInfo", data=payload, headers=api_headers, timeout=10, verify=False)
        
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
        print(f"TEFAS API Hatası ({fon_kodu}): {e}")

    # --- YÖNTEM 2: TEFAS Web Sayfası Parse ---
    try:
        web_res = session.get(f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu}", timeout=10, verify=False)
        if web_res.status_code == 200:
            price_match = re.search(r'MainContent_lblFiyat"[^>]*>([\d,\.]+)<', web_res.text) or \
                          re.search(r'Son Fiyat \(TL\)[\s\S]*?<span>([\d,\.]+)</span>', web_res.text)
            if price_match:
                price = float(price_match.group(1).replace(",", "."))
                change_match = re.search(r'MainContent_lblGunlukGetiri"[^>]*>([%+\-\d,\.]+)<', web_res.text)
                change_str = ""
                if change_match:
                    g_str = change_match.group(1).strip()
                    emoji = "🔴" if "-" in g_str else "🟢"
                    change_str = f" ({g_str} {emoji})"
                return price, change_str
    except Exception as e:
        print(f"TEFAS Web Hatası ({fon_kodu}): {e}")

    # --- YÖNTEM 3: Bigpara / Finans Yedek Kaynağı ---
    try:
        bp_res = session.get(f"https://bigpara.hurriyet.com.tr/borsa/fon-detay/{fon_kodu.upper()}/", timeout=10, verify=False)
        if bp_res.status_code == 200:
            price_match = re.search(r'class="[^"]*value[^"]*"[^>]*>([\d,\.]+)<', bp_res.text)
            if price_match:
                price = float(price_match.group(1).replace(",", ".").strip())
                change_match = re.search(r'class="[^"]*change[^"]*"[^>]*>([%+\-\d,\.]+)<', bp_res.text)
                change_str = ""
                if change_match:
                    c_str = change_match.group(1).strip()
                    emoji = "🔴" if "-" in c_str else "🟢"
                    change_str = f" ({c_str} {emoji})"
                return price, change_str
    except Exception as e:
        print(f"Yedek Kaynak Hatası ({fon_kodu}): {e}")

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
