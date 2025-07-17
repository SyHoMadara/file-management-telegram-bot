import asyncio
import logging
import os

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from apps.telegram_bot.handlers.commons import (
    help_command,
    start_command,
    language_command,
    language_callback,
)
from apps.telegram_bot.handlers.documents import handle_document
from config.settings import BASE_DIR

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_API_TOKEN", "")
API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

logger = logging.getLogger(__name__)

async def send_startup_notification(app):
    """Send notification to specific user when bot starts"""
    try:
        ADMIN_USER_ID = "103677626"

        if not ADMIN_USER_ID:
            logger.warning("⚠️ ADMIN_USER_ID not set - skipping startup notification")
            return

        startup_message = (
            "🚀 **Bot Started Successfully!**\n\n"
            "✅ Large File Bot is now online\n"
            "📅 Started at: {}\n"
            "🔧 Features available:\n"
            "• File uploads up to 2GB\n"
            "• Local Bot API Server\n"
            "• Rate limiting enabled\n\n"
            "Bot is ready to receive files! 📤"
        )

        from datetime import datetime

        formatted_message = startup_message.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # Try to send to user ID (integer)
        try:
            user_id = int(ADMIN_USER_ID)
            await app.send_message(user_id, formatted_message)
            logger.info(f"✅ Startup notification sent to user ID: {user_id}")
        except ValueError:
            # If not integer, try as username
            await app.send_message(ADMIN_USER_ID, formatted_message)
            logger.info(f"✅ Startup notification sent to username: @{ADMIN_USER_ID}")

    except Exception as e:
        logger.error(f"❌ Failed to send startup notification: {e}")
        # Don't stop the bot if notification fails


async def start_local_bot_async():
    """Start the bot with Local Bot API Server using Pyrogram"""
    if not BOT_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_API_TOKEN must be set in .env file")

    if not API_ID or not API_HASH:
        raise ValueError(
            "❌ TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env file"
        )

    logger.info("🚀 Starting Large File Bot with Pyrogram and Local Bot API Server")
    logger.info(f"🤖 Bot token: ...{BOT_TOKEN[-10:]}")

    logger.info(f"🔑 API ID: {API_ID}")

    app = Client(
        "file_management_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        workdir=str(BASE_DIR / "data" / "pyrogram"),
    )

    # Register handlers
    app.add_handler(MessageHandler(start_command, filters.command("start")))
    app.add_handler(MessageHandler(help_command, filters.command("help")))
    app.add_handler(
        MessageHandler(
            language_command, filters.command("lang") | filters.command("language")
        )
    )
    app.add_handler(MessageHandler(handle_document, filters.document))
    app.add_handler(CallbackQueryHandler(language_callback, filters.regex("^lang_")))

    logger.info("✅ Bot handlers registered successfully")
    logger.info("🔄 Starting bot...")

    # Start the bot
    async with app:
        logger.info("✅ Bot started successfully!")
        logger.info("🔄 Bot is now polling for messages...")
        await send_startup_notification(app)
        # Keep the bot running
        await asyncio.Event().wait()
