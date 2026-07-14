import os
import requests
import logging
import pickle
import asyncio
from telegram import Bot
from telegram.ext import ApplicationBuilder

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_URL = os.getenv("API_URL")

if not BOT_TOKEN or not CHAT_ID or not API_URL:
    logger.error("Missing environment variables: BOT_TOKEN, CHAT_ID, or API_URL")
    exit(1)

USER_API_URL = "https://olx.co.id{user_id}"
AD_URL = "https://olx.co.id{ad_id}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://olx.co.id",
    "Referer": "https://olx.co.id/"
}

notified_ads_file = 'notified_ads.pkl'

# Memuat database lama jika ada
if os.path.exists(notified_ads_file):
    with open(notified_ads_file, 'rb') as f:
        notified_ads = pickle.load(f)
else:
    notified_ads = set()

def filter_user_data(user_data):
    if not bool(user_data):
        return False
    if user_data.get('dealer') or user_data.get('is_business') or user_data.get('showroom_address'):
        return True
    return False

def fetch_user_data(user_id):
    if not user_id:
        return {}
    try:
        response = requests.get(USER_API_URL.format(user_id=user_id), headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json().get('data', {})
        return {}
    except:
        return {}

def fetch_ads():
    ads_data = {"ads": []}
    ads_data["previous_ads_count"] = len(notified_ads)
    
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data.get('data', [])
            
            # Ambil 20 iklan teratas untuk diperiksa
            for item in items[:20]:
                ad_id = item.get('ad_id', '')
                if not ad_id or ad_id in notified_ads:
                    continue
                
                user_id = item.get('user_id', '')
                user_data = fetch_user_data(user_id)
                if filter_user_data(user_data): 
                    continue

                price_data = item.get('price', {}).get('value', {})
                price_display = price_data.get('display', 'N/A') if isinstance(price_data, dict) else 'N/A'

                ads_data["ads"].append({
                    'ad_id': ad_id,
                    'title': item.get('title', 'N/A'),
                    'price': price_display,
                    'user_name': user_data.get('name', 'Individu'),
                    'ad_url': f"https://olx.co.id{ad_id}"
                })
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        
    return ads_data

async def send(bot, chat, msg):
    await bot.send_message(chat_id=chat, text=msg)

def notify_ads():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    ads_data = fetch_ads()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    count = 0
    # Jika database masih kosong (baru pertama jalan), masukkan semua iklan saat ini ke database tanpa mengirim notifikasi agar tidak spam
    if ads_data["previous_ads_count"] == 0:
        for ad in ads_data['ads']:
            notified_ads.add(ad['ad_id'])
        with open(notified_ads_file, 'wb') as f:
            pickle.dump(notified_ads, f)
        loop.run_until_complete(send(application.bot, CHAT_ID, "Bot Berhasil Diinisialisasi! Menunggu motor baru masuk..."))
    else:
        # Jika sudah ada database, kirim hanya iklan yang benar-benar baru
        for ad in ads_data['ads']:
            message = f"🏍️ MOTOR BARU OLX\n\nJudul: {ad['title']}\nHarga: {ad['price']}\nPenjual: {ad['user_name']}\n\nLink:\n{ad['ad_url']}"
            loop.run_until_complete(send(application.bot, CHAT_ID, message))
            notified_ads.add(ad['ad_id'])
            count += 1
            
        if count > 0:
            with open(notified_ads_file, 'wb') as f:
                pickle.dump(notified_ads, f)
                
    loop.close()

if __name__ == '__main__':
    notify_ads()
