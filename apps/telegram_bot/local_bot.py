import os
import logging
import requests
from io import BytesIO
from django.core.files.base import ContentFile
from dotenv import load_dotenv
from urllib.parse import urlsplit
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from apps.account.models import User
from apps.file_manager.models import FileManager
from config.settings import BASE_DIR

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_API_TOKEN", "")
API_SERVER = os.environ.get("TELEGRAM_API_SERVER", "http://localhost:8081")
base_minio_url = "http://" + os.environ.get("MINIO_EXTERNAL_ENDPOINT", "")

logger = logging.getLogger(__name__)

def create_user_if_not_exists(user_id):
    if not User.objects.filter(username=user_id).exists():
        User.objects.create(username=user_id)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads with Local Bot API Server (supports up to 2GB)"""
    try:
        document = update.message.document
        user_id = update.effective_user.id
        
        # Create user if not exists
        create_user_if_not_exists(user_id)
        
        # Check file size
        file_size = document.file_size
        max_size = 2 * 1024 * 1024 * 1024  # 2GB limit for Local Bot API
        
        if file_size > max_size:
            size_gb = file_size / (1024 * 1024 * 1024)
            await update.message.reply_text(
                f"❌ File too large ({size_gb:.1f}GB). Maximum file size is 2GB."
            )
            return
        
        # Send progress message
        size_mb = file_size / (1024 * 1024)
        progress_msg = await update.message.reply_text(
            f"📥 Downloading file...\n"
            f"📁 Name: {document.file_name}\n"
            f"📊 Size: {size_mb:.2f} MB\n"
            f"⏳ Please wait..."
        )
        
        # Get file from Local Bot API Server
        file = await context.bot.get_file(document.file_id)
        
        # Download file data
        file_data = BytesIO()
        await file.download_to_memory(file_data)
        
        # Update progress
        await progress_msg.edit_text(
            f"💾 Saving to storage...\n"
            f"📁 Name: {document.file_name}\n"
            f"📊 Size: {size_mb:.2f} MB"
        )
        
        # Save to database
        user = User.objects.get(username=user_id)
        file_data.seek(0)
        
        saved_file = FileManager.objects.create(
            user=user,
            name=document.file_name,
            file=ContentFile(file_data.getvalue(), name=document.file_name),
            file_size=file_size,
            file_mime_type=document.mime_type or 'application/octet-stream',
        )
        
        # Generate URL
        full_url = saved_file.file.url
        parsed_url = urlsplit(full_url)
        relative_path = parsed_url.path.lstrip('/') + '?' + parsed_url.query
        
        # Update with success message
        await progress_msg.edit_text(
            f"✅ File saved successfully!\n"
            f"📁 Name: {document.file_name}\n"
            f"📊 Size: {size_mb:.2f} MB\n"
            f"🔗 URL: {base_minio_url}/{relative_path}"
        )
        
        logger.info(f"File {document.file_name} saved successfully for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error saving file for user {update.effective_user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Error saving file: {str(e)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "🤖 Large File Storage Bot!\n\n"
        "📁 Send me any file up to 2GB and I'll store it.\n"
        "⚡ Using Local Bot API Server for large files.\n\n"
        "💡 Features:\n"
        "• Files up to 2GB (2048MB)\n"
        "• Fast downloads via local server\n"
        "• Direct storage to MinIO\n\n"
        "Just send a file to get started! 📤"
    )

def start_local_bot():
    """Start the bot with Local Bot API Server"""
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_API_TOKEN must be set")
    
    # Create bot instance with custom API server
    bot = Bot(token=BOT_TOKEN, base_url=f"{API_SERVER}/bot")
    
    # Create application
    application = Application.builder().bot(bot).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    logger.info("Starting Local Bot API bot...")
    
    # Start the bot
    application.run_polling(drop_pending_updates=True)
