import logging
import os
import tempfile
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlsplit

from pyrogram import Client
from pyrogram.types import Message

from apps.telegram_bot.utils.utils import (
    create_user_if_not_exists,
    get_user,
    is_rate_limited,
    save_file_to_db,
)
from config.settings import BASE_DIR

logger = logging.getLogger(__name__)

# Rate limiting setup - Adjust these for production
user_request_times = defaultdict(deque)
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("BOT_MAX_REQUESTS_PER_MINUTE", "5"))
CONCURRENT_DOWNLOADS = 0
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("BOT_MAX_CONCURRENT_DOWNLOADS", "3"))

# Environment variables
base_minio_url = "http://" + os.environ.get("MINIO_EXTERNAL_ENDPOINT", "")


async def handle_document(client: Client, message: Message):
    """Handle document uploads with Pyrogram and Local Bot API Server (supports up to 2GB)"""
    global CONCURRENT_DOWNLOADS

    user_id = message.from_user.id

    # Check rate limit
    if is_rate_limited(user_id):
        await message.reply_text(
            "⚠️ Rate limit exceeded!\n"
            f"📊 You can upload max {MAX_REQUESTS_PER_MINUTE} files per minute.\n"
            "⏳ Please wait before sending another file."
        )
        return

    try:
        document = message.document
        if not document:
            await message.reply_text("❌ No document found in the message.")
            return

        # Create user if not exists
        user_created = await create_user_if_not_exists(user_id)
        if user_created:
            logger.info(f"Created new user: {user_id}")
        user = await get_user(user_id)
        # Check file size
        file_size = document.file_size
        max_size = (
            user.remaining_download_size * 1024 * 1024
        )

        # Log file details for debugging
        logger.info(
            f"User: {user.username}, Processing file: {document.file_name}, Size: {file_size} bytes ({file_size / (1024 * 1024):.2f} MB)"
        )

        if file_size > max_size:
            size_gb = file_size / (1024 * 1024 * 1024)
            await message.reply_text(
                f"❌ File too large ({size_gb:.1f}GB). Maximum download remaining is {user.remaining_download_size}MB."
            )
            return

        # Send progress message
        size_mb = file_size / (1024 * 1024)
        progress_msg = await message.reply_text(
            f"📥 Downloading file...\n"
            f"📁 Name: {document.file_name}\n"
            f"📊 Size: {size_mb:.2f} MB\n"
            f"⏳ Please wait..."
        )

        # Check concurrent download limit
        if CONCURRENT_DOWNLOADS >= MAX_CONCURRENT_DOWNLOADS:
            await message.reply_text(
                "⏳ Server busy! Too many downloads in progress.\n"
                f"📊 Current limit: {MAX_CONCURRENT_DOWNLOADS} concurrent downloads\n"
                "🔄 Please try again in a moment."
            )
            return

        # TODO add celery for downloads and file type checking with magic
        CONCURRENT_DOWNLOADS += 1
        try:
            # Create temporary file for downloading
            temp_dir = Path(BASE_DIR) / "data" / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as temp_file:
                temp_file_path = temp_file.name

                # Download file using Pyrogram (automatically uses Local Bot API Server)
                try:
                    logger.info("Downloading file using Pyrogram")
                    logger.info(f"File ID: {document.file_id}, File size: {file_size}")

                    # Download the file directly to the temp location
                    await client.download_media(message, file_name=temp_file_path)

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

            user.remaining_download_size -= file_size / (1024 * 1024)
            await user.save(update_fields=["remaining_download_size"])

            logger.info(
                f"File {document.file_name} saved successfully for user {user_id}"
            )

        except Exception as e:
            logger.error(
                f"Error saving file for user {user_id}: {str(e)}",
                exc_info=True,
            )
            await message.reply_text("❌ Error saving file")

    finally:
        CONCURRENT_DOWNLOADS -= 1
