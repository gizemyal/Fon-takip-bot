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

def get_fund_data_tefas_api(session, fon_kodu):
    """Yöntem 1: TEFAS API üzerinden veri çeker."""
    url = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.tefas.gov.tr",
        "Referer": f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu}"
    }

    res = session.post(url, data=payload, headers=headers, timeout=12, verify=False)
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
        else:
            return None, "Boş Veri"
    else:
        return None, f"API HTTP {res.status_code}"

def get_fund_data_tefas_web(session, fon_kodu):
    """Yöntem 2: TEFAS Web (FonAnaliz) sayfasından doğrudan fiyat okur."""
    url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    res = session.get(url, headers=headers, timeout=12, verify=False)
    if res.status_code == 200:
        # Fiyat bilgisini çekme
        match = re.search(r'id="MainContent_lblFiyat"[^>]*>([\d,\.]+)<', res.text)
        if match:
            price_str = match.group(1).replace(",", ".")
            price = float(price_str)
            
            # Günlük getiri bilgisini çekme
            getiri_match = re.search(r'id="MainContent_lblGunlukGetiri"[^>]*>([%+\-\d,\.]+)<', res.text)
            change_str = ""
            if getiri_match:
                g_str = getiri_match.group(1).strip()
                emoji = "🔴" if "-" in g_str else "🟢"
                change_str = f" ({g_str} {emoji})"
            return price, change_str
        return None, "Parse Edilemedi"
    return None, f"Web HTTP {res.status_code}"

def fetch_fund_data(fon_kodu):
    session = requests.Session()
    session.mount('https://', LegacySSLAdapter())
    
    # TEFAS'tan Session Cookie alalım
    try:
        session.get("https://www.tefas.gov.tr/", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=8, verify=False)
    except Exception:
        pass

    # Yöntem 1: API
    try:
        price, change = get_fund_data_tefas_api(session, fon_kodu)
        if price is not None:
            return price, change
        err_api = change
    except Exception as e:
        err_api = str(e)[:25]

    # Yöntem 2: Web Sayfası
    try:
        price, change = get_fund_data_tefas_web(session, fon_kodu)
        if price is not None:
            return price, change
        err_web = change
    except Exception as e:
        err_web = str(e)[:25]

    return None, f"API: {err_api} | Web: {err_web}"

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
        price, change = fetch_fund_data(kod)
        icon = icons.get(kod, "🔹")
        if price is not None:
            lines.append(f"{icon} *{kod}:* {price:.4f} TL{change}")
        else:
            lines.append(f"{icon} *{kod}:* Veri alınamadı ({change})")

    msg = "\n".join(lines)
    send_telegram_message(msg)

if __name__ == "__main__":
    main()
