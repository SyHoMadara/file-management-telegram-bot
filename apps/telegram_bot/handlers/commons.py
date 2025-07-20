import logging
from django.utils.translation import activate, get_language, gettext_lazy as _
from pyrogram.client import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

# In-memory user language storage (replace with DB in production)
user_language_preferences = {}

def get_user_language(message: Message) -> str:
    user_id = message.from_user.id
    
    if user_id in user_language_preferences:
        return user_language_preferences[user_id]

    lang_code = getattr(message.from_user, "language_code", "en").lower()
    if lang_code.startswith("fa") or lang_code.startswith("pe"):
        return "fa"
    if lang_code.startswith("en"):
        return "en"

    return "en"

def set_user_language(user_id: int, language: str):
    user_language_preferences[user_id] = language
    logger.info(f"Set language '{language}' for user {user_id}")

def activate_user_language(message: Message):
    user_lang = get_user_language(message)
    activate(user_lang)
    logger.info(f"Activated language '{user_lang}' for user {message.from_user.id}")

async def start_command(client: Client, message: Message):
    activate_user_language(message)

    start_message = _(
        "🤖 Large File Storage Bot!\n\n"
        "📁 Send me any file and I'll store it.\n\n"
        "Just send a file to get started! 📤"
    )

    logger.info(f"Sending start message in language: {get_language()}")
    await message.reply_text(str(start_message))

async def help_command(client: Client, message: Message):
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
    )

    logger.info(f"Sending help message in language: {get_language()}")
    await message.reply_text(str(help_message))

async def language_command(client: Client, message: Message):
    activate_user_language(message)

    current_lang = get_user_language(message)
    current_lang_name = "Persian" if current_lang == "fa" else "English"

    lang_message = _(
        "🌐 Language Settings\n\n"
        "Current language: %(current_lang)s\n\n"
        "Please select your preferred language:"
    ) % {"current_lang": current_lang_name}

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang_fa"),
        ]
    ])

    await message.reply_text(str(lang_message), reply_markup=keyboard)

async def language_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data.startswith("lang_"):
        selected_lang = data.split("_")[1]
        set_user_language(user_id, selected_lang)
        activate(selected_lang)

        lang_name = "Persian" if selected_lang == "fa" else "English"

        confirmation_message = _(
            "✅ Language changed successfully!\n\n"
            "Your language is now set to: %(lang_name)s\n\n"
            "All bot messages will now be displayed in your selected language."
        ) % {"lang_name": lang_name}

        await callback_query.edit_message_text(str(confirmation_message))

        await callback_query.answer(
            str(_("Language changed to %(lang_name)s") % {"lang_name": lang_name})
        )

        logger.info(f"User {user_id} changed language to {selected_lang}")
