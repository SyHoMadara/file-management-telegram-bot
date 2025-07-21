import logging
from django.utils.translation import activate, get_language, gettext_lazy as _
from django.utils import timezone
from asgiref.sync import sync_to_async
from pyrogram.client import Client
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from apps.account.models import User

logger = logging.getLogger(__name__)

# Admin user ID (should be configurable in production)
ADMIN_USER_ID = "103677626"

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
        "📁 Send me any file and I'll store it.\n"
        "🔗 Send me a video link and I'll download it for you.\n\n"
        "Just send a file or link to get started! 📤"
    )

    logger.info(f"Sending start message in language: {get_language()}")
    await message.reply_text(str(start_message))

async def help_command(client: Client, message: Message):
    activate_user_language(message)

    help_message = _(
        "🆘 Help - Large File Storage Bot\n\n"
        "📋 Available Commands:\n"
        "• /start - Show welcome message\n"
        "• /help - Show this help message\n"
        "• /premium - Request premium access\n\n"
        "📤 How to use:\n"
        "1. Simply send any document to the bot\n"
        "2. Wait for the upload to complete\n"
        "3. Get your download URL\n\n"
        "💎 Premium features:\n"
        "• Unlimited daily downloads\n"
        "• Priority processing\n"
        "• Enhanced download speeds\n\n"
        "Use /premium to request premium access!\n"
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

async def premium_command(client: Client, message: Message):
    """Handle /premium command - allows users to request premium access"""
    activate_user_language(message)
    
    user_id = message.from_user.id
    
    try:
        # Get or create user in database (async)
        user, created = await sync_to_async(User.objects.get_or_create)(
            telegram_id=message.from_user.username,
            defaults={
                'username': message.from_user.id,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
            }
        )
        
        # Update user info every time (in case user changed name/username)
        if not created:
            user.telegram_id = message.from_user.username
            user.username = message.from_user.id
            user.first_name = message.from_user.first_name
            user.last_name = message.from_user.last_name
            await sync_to_async(user.save)(update_fields=['username', 'first_name', 'last_name', 'telegram_id'])
        
        # Check if user is already premium
        if user.is_premium:
            premium_active_message = _(
                "✅ You already have premium access!\n\n"
                "🌟 Premium features are active for your account.\n"
                "Enjoy unlimited downloads!"
            )
            await message.reply_text(str(premium_active_message))
            return
            
        # Check if user has already requested premium
        if user.premium_requested:
            already_requested_message = _(
                "⏳ You have already sent a premium request!\n\n"
                "🔄 Your request is being reviewed by administrators.\n"
                "You will be notified once your request is processed.\n\n"
                "Please be patient and avoid sending multiple requests."
            )
            await message.reply_text(str(already_requested_message))
            return
            
        # Mark user as having requested premium (async)
        user.premium_requested = True
        user.premium_request_date = timezone.now()
        await sync_to_async(user.save)(update_fields=['premium_requested', 'premium_request_date'])
        
        # Send confirmation to user
        request_sent_message = _(
            "📨 Premium request sent successfully!\n\n"
            "✅ Your request has been forwarded to administrators.\n"
            "🔔 You will be notified once your request is reviewed.\n\n"
            "Thank you for your interest in premium features!"
        )
        await message.reply_text(str(request_sent_message))
        
        # Notify admin about the premium request
        try:
            admin_notification = (
                f"🔔 **New Premium Request**\n\n"
                f"👤 **User:** {message.from_user.first_name or 'Unknown'} "
                f"{message.from_user.last_name or ''}\n"
                f"🆔 **User ID:** `{user_id}`\n"
                f"📱 **Username:** @{message.from_user.username or 'None'}\n"
                f"📅 **Request Date:** {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"💎 User is requesting premium access. Please review and process accordingly."
            )
            
            await client.send_message(int(ADMIN_USER_ID), admin_notification)
            logger.info(f"Premium request notification sent to admin for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send premium request notification to admin: {e}")
            
    except Exception as e:
        logger.error(f"Error processing premium request for user {user_id}: {e}")
        error_message = _(
            "❌ Sorry, there was an error processing your request.\n\n"
            "Please try again later or contact support."
        )
        await message.reply_text(str(error_message))
