import os
import logging
import requests
import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import MongoClient
from dotenv import load_dotenv

# Load env
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMAVEN_API_KEY = os.getenv("ADMAVEN_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Correct AdMaven API endpoint
ADMAVEN_API_URL = "https://publishers.ad-maven.com/api/public/content_locker"

# Logging
logging.basicConfig(level=logging.INFO)

# DB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["admaven_bot"]
links_col = db["links"]

# Bot
app = Client("ad_maven_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


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
    await callback_query.message.reply_text("🔗 Send me the original link you want to monetize.")
    await callback_query.answer()


@app.on_message(filters.text & ~filters.command("start"))
async def handle_link(client, message):
    user_id = message.from_user.id
    original_url = message.text.strip()

    payload = {
        "api_key": ADMAVEN_API_KEY,
        "url": original_url
    }

    try:
        # AdMaven expects form-encoded data
        response = requests.post(ADMAVEN_API_URL, data=payload)
        data = response.json()

        if data.get("status") == "success":
            short_url = data["link"]

            # Save to MongoDB
            links_col.insert_one({
                "user_id": user_id,
                "original_url": original_url,
                "short_url": short_url,
                "created_at": datetime.datetime.utcnow()
            })

            await message.reply_text(f"✅ Your monetized link:\n\n{short_url}")
        else:
            await message.reply_text("⚠️ Failed to generate link. Please try again later.")
    except Exception as e:
        logging.error(f"Error: {e}")
        await message.reply_text("❌ Error occurred while generating link.")


@app.on_callback_query(filters.regex("my_links"))
async def show_links(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user_links = list(links_col.find({"user_id": user_id}).sort("created_at", -1))

    if not user_links:
        await callback_query.message.reply_text("📭 You haven’t generated any links yet.")
    else:
        text = "📜 **Your Links:**\n\n"
        for link in user_links[:10]:  # show latest 10
            text += f"🔗 {link['original_url']} → {link['short_url']}\n\n"

        await callback_query.message.reply_text(text)

    await callback_query.answer()


app.run()
