import logging
import os

from pyrogram import Client
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# Get environment variables for display
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("BOT_MAX_REQUESTS_PER_MINUTE", "5"))
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("BOT_MAX_CONCURRENT_DOWNLOADS", "3"))


async def start_command(client: Client, message: Message):
    """Start command handler"""
    await message.reply_text(
        "🤖 Large File Storage Bot!\n\n"
        "📁 Send me any file up to 2GB and I'll store it.\n\n"
        "💡 Features:\n"
        "• Files up to 2GB (2048MB)\n"
        "• Fast downloads via local server\n"
        "• Direct storage to MinIO\n\n"
        "⚠️ Rate Limits:\n"
        f"• Max {MAX_REQUESTS_PER_MINUTE} files per minute per user\n"
        f"• Max {MAX_CONCURRENT_DOWNLOADS} downloads at once\n\n"
        "Just send a file to get started! 📤"
    )


async def help_command(client: Client, message: Message):
    """Help command handler"""
    await message.reply_text(
        "🆘 Help - Large File Storage Bot\n\n"
        "📋 Available Commands:\n"
        "• /start - Show welcome message\n"
        "• /help - Show this help message\n\n"
        "📤 How to use:\n"
        "1. Simply send any document to the bot\n"
        "2. Wait for the upload to complete\n"
        "3. Get your download URL\n\n"
        "📏 File Limits:\n"
        f"• Maximum file size: 2GB (2048MB)\n"
        f"• Rate limit: {MAX_REQUESTS_PER_MINUTE} files per minute\n"
        f"• Concurrent uploads: {MAX_CONCURRENT_DOWNLOADS}\n\n"
        "🔧 Supported file types:\n"
        "• Documents, archives, videos, images\n"
        "• Any file type up to 2GB\n\n"
        "❓ Having issues?\n"
        "• Make sure your file is under 2GB\n"
        "• Wait between uploads if rate limited\n"
        "• Try again if upload fails"
    )
