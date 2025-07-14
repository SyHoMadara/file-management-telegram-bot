import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from telegram import Update
from telegram.ext import ContextTypes

from apps.telegram_bot.utils.utils import (
    create_user_if_not_exists,
    get_user,
    is_rate_limited,
    save_file_to_db,
)
from config.settings import BASE_DIR

logger = logging.getLogger(__name__)

# Rate limiting setup - Adjust these for production

MAX_REQUESTS_PER_MINUTE = int(os.environ.get("BOT_MAX_REQUESTS_PER_MINUTE", "5"))
CONCURRENT_DOWNLOADS = 0
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("BOT_MAX_CONCURRENT_DOWNLOADS", "3"))

# Environment variables
base_minio_url = "http://" + os.environ.get("MINIO_EXTERNAL_ENDPOINT", "")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads with Local Bot API Server (supports up to 2GB)"""
    global CONCURRENT_DOWNLOADS

    user_id = update.effective_user.id

    # Check rate limit
    if is_rate_limited(user_id):
        await update.message.reply_text(
            "⚠️ Rate limit exceeded!\n"
            f"📊 You can upload max {MAX_REQUESTS_PER_MINUTE} files per minute.\n"
            "⏳ Please wait before sending another file."
        )
        return

    try:
        document = update.message.document

        # Create user if not exists
        user_created = await create_user_if_not_exists(user_id)
        if user_created:
            logger.info(f"Created new user: {user_id}")

        # Check file size
        file_size = document.file_size
        max_size = 2 * 1024 * 1024 * 1024  # 2GB limit for Local Bot API

        # Log file details for debugging
        logger.info(
            f"Processing file: {document.file_name}, Size: {file_size} bytes ({file_size / (1024 * 1024):.2f} MB)"
        )

        if file_size > max_size:
            size_gb = file_size / (1024 * 1024 * 1024)
            await update.message.reply_text(
                f"❌ File too large ({size_gb:.1f}GB). Maximum file size is 2GB."
            )
            return

        # Check if file might be too big for standard Bot API (20MB)
        standard_limit = 20 * 1024 * 1024  # 20MB
        if file_size > standard_limit:
            logger.warning(
                f"File {document.file_name} ({file_size / (1024 * 1024):.2f}MB) exceeds standard Bot API limit (20MB). Requires Local Bot API Server."
            )

        # Send progress message
        size_mb = file_size / (1024 * 1024)
        progress_msg = await update.message.reply_text(
            f"📥 Downloading file...\n"
            f"📁 Name: {document.file_name}\n"
            f"📊 Size: {size_mb:.2f} MB\n"
            f"⏳ Please wait..."
        )

        # Check concurrent download limit
        if CONCURRENT_DOWNLOADS >= MAX_CONCURRENT_DOWNLOADS:
            await update.message.reply_text(
                "⏳ Server busy! Too many downloads in progress.\n"
                f"📊 Current limit: {MAX_CONCURRENT_DOWNLOADS} concurrent downloads\n"
                "🔄 Please try again in a moment."
            )
            return

        # TODO add celery for downloads
        CONCURRENT_DOWNLOADS += 1
        try:
            # Get file from Local Bot API Server
            try:
                file = await context.bot.get_file(document.file_id)
                logger.info(
                    f"File info received: path={file.file_path}, size={file.file_size}"
                )
            except Exception as e:
                logger.error(f"Failed to get file info: {str(e)}")
                await progress_msg.edit_text(
                    f"❌ File access failed!\n"
                    f"📁 Name: {document.file_name}\n"
                    f"📊 Size: {size_mb:.2f} MB\n\n"
                    f"🚨 Error: {str(e)}\n\n"
                    f"💡 This might indicate:\n"
                    f"• Local Bot API Server issues\n"
                    f"• File too large for current setup\n"
                    f"• Network connectivity problems"
                )
                return

            # Create temporary file for streaming download
            temp_dir = Path(BASE_DIR) / "data" / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as temp_file:
                temp_file_path = temp_file.name

                # Download file directly to disk (streaming)
                try:
                    # Use the telegram library's built-in download method
                    # This handles Local Bot API Server automatically
                    logger.info("Downloading file using telegram library method")
                    logger.info(
                        f"File path: {file.file_path}, File size: {file.file_size}"
                    )

                    # Download the file directly to the temp location
                    await file.download_to_drive(temp_file_path)

                    logger.info(
                        f"File downloaded to temporary location: {temp_file_path}"
                    )

                except Exception as download_error:
                    logger.error(
                        f"Download failed for {document.file_name}: {str(download_error)}"
                    )
                    logger.error(
                        "This might indicate Local Bot API Server issues or file access problems"
                    )
                    await progress_msg.edit_text(
                        f"❌ File download failed!\n"
                        f"📁 Name: {document.file_name}\n"
                        f"📊 Size: {size_mb:.2f} MB\n\n"
                        f"🚨 Error: {str(download_error)}\n\n"
                        f"💡 Possible causes:\n"
                        f"• Local Bot API Server not properly configured\n"
                        f"• File too large for current setup\n"
                        f"• Network connectivity issues\n\n"
                        f"🔧 Check logs:\n"
                        f"`docker-compose -f docker-compose-bot.yml logs telegram-bot-api`"
                    )
                    # Clean up the temp file if it was created
                    try:
                        os.unlink(temp_file_path)
                    except Exception:
                        pass
                    return

            # Update progress
            await progress_msg.edit_text(
                f"💾 Saving to storage...\n"
                f"📁 Name: {document.file_name}\n"
                f"📊 Size: {size_mb:.2f} MB"
            )

            # Save to database using file path (no memory loading)
            user = await get_user(user_id)

            try:
                saved_file = await save_file_to_db(
                    user,
                    document.file_name,
                    temp_file_path,
                    file_size,
                    document.mime_type,
                )
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Temporary file cleaned up: {temp_file_path}")
                except OSError as e:
                    logger.warning(
                        f"Failed to clean up temporary file {temp_file_path}: {e}"
                    )

            # Generate URL
            full_url = saved_file.file.url
            parsed_url = urlsplit(full_url)
            relative_path = parsed_url.path.lstrip("/") + "?" + parsed_url.query

            # Update with success message
            await progress_msg.edit_text(
                f"✅ File saved successfully!\n"
                f"📁 Name: {document.file_name}\n"
                f"📊 Size: {size_mb:.2f} MB\n"
                f"🔗 URL: {base_minio_url}/{relative_path}"
            )

            logger.info(
                f"File {document.file_name} saved successfully for user {user_id}"
            )

        except Exception as e:
            logger.error(
                f"Error saving file for user {update.effective_user.id}: {str(e)}",
                exc_info=True,
            )
            await update.message.reply_text(f"❌ Error saving file: {str(e)}")

    finally:
        CONCURRENT_DOWNLOADS -= 1
