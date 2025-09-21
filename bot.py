import os
import logging
import requests
import datetime
import sqlite3
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Fixed API credentials
API_ID = "19662976"
API_HASH = "97cfb26df0a49ab11fa482a5bf660019"
BOT_TOKEN = "8225710278:AAFrkhQ7Q_89NlKsvm57cdYSDlTHVyVFYQA"
ADMAVEN_API_TOKEN = "c5d33697568f605fbda0ed91f66569739e87338e31611cb98392d4672fc78af3"

ADMAVEN_API_URL = "https://publishers.ad-maven.com/api/public/content_locker"

logging.basicConfig(level=logging.INFO)

# SQLite database setup
DB_FILE = "admaven_bot.db"

def init_database():
    """Initialize SQLite database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            original_url TEXT NOT NULL,
            short_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def save_link(user_id, original_url, short_url):
    """Save a link to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO links (user_id, original_url, short_url, created_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, original_url, short_url, datetime.datetime.utcnow()))
    
    conn.commit()
    conn.close()

def get_user_links(user_id, limit=10):
    """Get user's links from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT original_url, short_url, created_at
        FROM links
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (user_id, limit))
    
    links = cursor.fetchall()
    conn.close()
    return links

# Initialize database
init_database()


app = Client("ad_maven_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


awaiting_link = {}

@app.on_message(filters.command("start"))
async def start(client, message):
    buttons = [
        [InlineKeyboardButton("➕ Generate Link", callback_data="generate")],
        [InlineKeyboardButton("📜 My Links", callback_data="my_links")]
    ]
    await message.reply_text(
        "👋 You can use me to create links from AdMaven.\n\nChoose an option below:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_callback_query(filters.regex("generate"))
async def ask_link(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    awaiting_link[user_id] = True 
    await callback_query.message.reply_text("🔗 Send me the original link you want to monetize.")
    await callback_query.answer()


@app.on_message(filters.text & ~filters.command("start"))
async def handle_link(client, message):
    user_id = message.from_user.id
    original_url = message.text.strip()

    if not awaiting_link.get(user_id):
        return

    awaiting_link[user_id] = False

    try:
        headers = {
            "Authorization": f"Bearer {ADMAVEN_API_TOKEN}",
            "Content-Type": "application/json"
        }

        data = {
            "title": "Generated via Telegram Bot",
            "url": original_url,   
            "background": ""  # Optional, can be omitted or an empty string
        }

        response = requests.post(ADMAVEN_API_URL, headers=headers, json=data)
        try:
            data = response.json()
        except Exception:
            await message.reply_text(f"❌ Invalid response from API:\n{response.text}")
            return

        if data.get("type") == "created":
            # Try to extract the short URL
            api_message = data.get("message")
            if isinstance(api_message, list) and len(api_message) > 0:
                # If message is a list, get the first item
                first_item = api_message[0]
                short_url = first_item.get("full_short")  # Use 'full_short' instead of 'desturl'
            elif isinstance(api_message, dict):
                # If message is a dict, get full_short directly
                short_url = api_message.get("full_short")
            else:
                await message.reply_text(f"⚠️ Unexpected message format: {api_message}")
                return
            
            if short_url:
                save_link(user_id, original_url, short_url)
                await message.reply_text(f"✅ Your monetized link:\n\n{short_url}")
            else:
                await message.reply_text(f"⚠️ No short URL found in response: {data}")
        else:
            await message.reply_text(f"⚠️ Failed to generate link.\nResponse: {data}")

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.reply_text(f"❌ Exception occurred: {str(e)}")


@app.on_callback_query(filters.regex("my_links"))
async def show_links(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user_links = get_user_links(user_id)

    if not user_links:
        await callback_query.message.reply_text("📭 You haven't generated any links yet.")
    else:
        text = "📜 **Your Links:**\n\n"
        for link in user_links:  
            original_url, short_url, created_at = link
            text += f"🔗 {original_url} → {short_url}\n\n"

        await callback_query.message.reply_text(text)

    await callback_query.answer()


app.run()
