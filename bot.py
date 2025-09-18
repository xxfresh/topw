import os
import logging
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ENV values
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMAVEN_API_KEY = os.getenv("ADMAVEN_API_KEY")

# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["adtopg"]
links_collection = db["links"]

# AdMaven API
ADMAVEN_API_URL = "https://publishers.ad-maven.com/api/public/content_locker"


def generate_admaven_link(title: str, url: str, background: str = None):
    """Send request to AdMaven API and return result or error"""
    try:
        headers = {
            "Authorization": f"Bearer {ADMAVEN_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "title": title,
            "url": url
        }
        if background:
            payload["background"] = background

        response = requests.post(ADMAVEN_API_URL, json=payload, headers=headers)

        # Try parsing JSON
        try:
            data = response.json()
        except Exception:
            return None, f"❌ Invalid JSON response: {response.text}"

        if data.get("type") == "created":
            return data["message"]["desturl"], None

        # Debugging → return raw API response
        return None, f"⚠️ Failed to generate link.\nAPI Response: {data}"

    except Exception as e:
        return None, f"❌ Exception occurred: {str(e)}"


# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Generate Link", callback_data="generate_link")],
        [InlineKeyboardButton("📜 My Links", callback_data="list_links")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome! I can help you generate AdMaven content locker links.\n\n"
        "Choose an option below:",
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "generate_link":
        await query.message.reply_text("🔗 Send me the URL you want to lock:")
        context.user_data["awaiting_url"] = True

    elif query.data == "list_links":
        user_id = update.effective_user.id
        user_links = links_collection.find({"user_id": user_id})

        if user_links.count() == 0:
            await query.message.reply_text("📭 You haven't generated any links yet.")
        else:
            text = "📜 *Your Generated Links:*\n\n"
            for idx, link in enumerate(user_links, 1):
                text += f"{idx}. [{link['title']}]({link['desturl']})\n"
            await query.message.reply_text(text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_url"):
        url = update.message.text.strip()
        context.user_data["awaiting_url"] = False

        await update.message.reply_text("⏳ Generating your AdMaven link...")

        link, error = generate_admaven_link("Generated Link", url)

        if link:
            links_collection.insert_one({
                "user_id": update.effective_user.id,
                "title": "Generated Link",
                "url": url,
                "desturl": link
            })
            await update.message.reply_text(f"✅ Link generated:\n{link}")
        else:
            await update.message.reply_text(error)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
