import logging
import os

from django.utils.translation import gettext_lazy as _, activate, get_language
from django.utils import translation
from pyrogram import Client
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

logger = logging.getLogger(__name__)

# Get environment variables for display
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("BOT_MAX_REQUESTS_PER_MINUTE", "5"))
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("BOT_MAX_CONCURRENT_DOWNLOADS", "3"))

# Store user language preferences (in production, use database)
user_language_preferences = {}


def get_user_language(message: Message) -> str:
    """Get user's preferred language"""
    user_id = message.from_user.id

    # Check if user has a stored preference
    if user_id in user_language_preferences:
        return user_language_preferences[user_id]

    # Try to get language from user's Telegram client
    if hasattr(message.from_user, "language_code") and message.from_user.language_code:
        lang_code = message.from_user.language_code.lower()
        # Map common language codes to our supported languages
        if lang_code.startswith("fa") or lang_code.startswith("pe"):
            return "fa"
        elif lang_code.startswith("en"):
            return "en"

    # Default fallback
    return "en"


def set_user_language(user_id: int, language: str):
    """Set user's preferred language"""
    user_language_preferences[user_id] = language
    logger.info(f"Set language '{language}' for user {user_id}")


def activate_user_language(message: Message):
    """Activate translation for the user's preferred language"""
    user_lang = get_user_language(message)
    activate(user_lang)
    logger.info(f"Activated language '{user_lang}' for user {message.from_user.id}")


async def start_command(client: Client, message: Message):
    """Start command handler"""
    # Activate user's language
    activate_user_language(message)

    start_message = _(
        "🤖 Large File Storage Bot!\n\n"
        "📁 Send me any file and I'll store it.\n\n"
        "💡 Features:\n"
        "• Files up to 2GB (2048MB)\n"
        "• Fast downloads via local server\n"
        "• Direct storage to MinIO\n\n"
        "⚠️ Rate Limits:\n"
        "• Max %(max_requests)d files per minute per user\n"
        "• Max %(max_downloads)d downloads at once\n\n"
        "Just send a file to get started! 📤"
    ) % {
        "max_requests": MAX_REQUESTS_PER_MINUTE,
        "max_downloads": MAX_CONCURRENT_DOWNLOADS,
    }

    current_lang = get_language()
    logger.info(f"Sending start message in language: {current_lang}")

    await message.reply_text(str(start_message))


async def help_command(client: Client, message: Message):
    """Help command handler"""
    # Activate user's language
    activate_user_language(message)

    help_message = _(
        "🆘 Help - Large File Storage Bot\n\n"
        "📋 Available Commands:\n"
        "• /start - Show welcome message\n"
        "• /help - Show this help message\n\n"
        "📤 How to use:\n"
        "1. Simply send any document to the bot\n"
        "2. Wait for the upload to complete\n"
        "3. Get your download URL\n\n"
        "� File Limits:\n"
        f"• Maximum file size: 2GB (2048MB)\n"
        f"• Rate limit: {MAX_REQUESTS_PER_MINUTE} files per minute\n"
        f"• Concurrent uploads: {MAX_CONCURRENT_DOWNLOADS}\n\n"
        "�🔧 Supported file types:\n"
        "• Documents, archives, videos, images\n"
        "• Any file type up to 2GB\n\n"
        "❓ Having issues?\n"
        "• Make sure your file is under 2GB\n"
        "• Wait between uploads if rate limited\n"
        "• Try again if upload fails"
    ) 

    current_lang = get_language()
    logger.info(f"Sending help message in language: {current_lang}")

    await message.reply_text(str(help_message))


async def language_command(client: Client, message: Message):
    """Language selection command"""
    activate_user_language(message)

    current_lang = get_user_language(message)
    current_lang_name = "Persian" if current_lang == "fa" else "English"

    lang_message = _(
        "🌐 Language Settings\n\n"
        "Current language: %(current_lang)s\n\n"
        "Please select your preferred language:"
    ) % {"current_lang": current_lang_name}

    # Create inline keyboard with language options
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
                InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang_fa"),
            ]
        ]
    )

    await message.reply_text(str(lang_message), reply_markup=keyboard)


async def language_callback(client: Client, callback_query: CallbackQuery):
    """Handle language selection callback"""
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data.startswith("lang_"):
        selected_lang = data.split("_")[1]  # Extract 'en' or 'fa'

        # Set user's language preference
        set_user_language(user_id, selected_lang)

        # Activate the selected language
        activate(selected_lang)

        # Get language name for confirmation
        lang_name = "Persian" if selected_lang == "fa" else "English"

        # Send confirmation message in the selected language
        confirmation_message = _(
            "✅ Language changed successfully!\n\n"
            "Your language is now set to: %(lang_name)s\n\n"
            "All bot messages will now be displayed in your selected language."
        ) % {"lang_name": lang_name}

        # Edit the message to show confirmation
        await callback_query.edit_message_text(str(confirmation_message))

        # Answer the callback query
        await callback_query.answer(
            str(_("Language changed to %(lang_name)s") % {"lang_name": lang_name})
        )

        logger.info(f"User {user_id} changed language to {selected_lang}")
