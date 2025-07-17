import logging
import os
from collections import defaultdict, deque
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional
from urllib.parse import urlsplit

from asgiref.sync import sync_to_async
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

# Configuration constants
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("BOT_MAX_REQUESTS_PER_MINUTE", "5"))
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("BOT_MAX_CONCURRENT_DOWNLOADS", "3"))
MINIO_BASE_URL = f"http://{os.environ.get('MINIO_EXTERNAL_ENDPOINT', '')}"

# Global state
user_request_times = defaultdict(deque)
concurrent_downloads = 0


class FileProcessingError(Exception):
    """Custom exception for file processing errors."""

    pass


async def handle_document(client: Client, message: Message) -> None:
    """
    Handle document uploads with Pyrogram and Local Bot API Server (supports up to 2GB).

    Args:
        client: Pyrogram Client instance
        message: Pyrogram Message containing the document
    """
    global concurrent_downloads

    if not message.document:
        await message.reply_text(
            "🚫 **No Document Found**\nPlease send a valid file to upload."
        )
        return

    user_id = message.from_user.id
    document = message.document

    try:
        # Rate limiting check
        if is_rate_limited(user_id):
            await _send_rate_limit_message(message)
            return

        # User validation and creation
        user = await _validate_and_get_user(user_id)
        if not user:
            return

        # File size validation
        if not _is_file_size_valid(document.file_size, user):
            await _send_file_size_error_message(message, document, user)
            return

        # Concurrent downloads check
        if not _can_process_download():
            await _send_concurrent_limit_message(message)
            return

        # Process file download and storage
        await _process_file(client, message, document, user)

    except FileProcessingError as e:
        logger.error(f"File processing failed for user {user_id}: {str(e)}")
        await message.reply_text(
            "😔 **Error Processing File**\n"
            "Something went wrong. Please try again later."
        )
    except Exception as e:
        logger.error(f"Unexpected error for user {user_id}: {str(e)}", exc_info=True)
        await message.reply_text(
            "😔 **Unexpected Error**\n"
            "An unexpected issue occurred. Please try again later."
        )


async def _send_rate_limit_message(message: Message) -> None:
    """Send rate limit exceeded message."""
    await message.reply_text(
        "⏱ **Rate Limit Reached**\n"
        f"You've hit the limit of {MAX_REQUESTS_PER_MINUTE} uploads per minute.\n"
        "Please wait a moment and try again! 🕒"
    )


async def _validate_and_get_user(user_id: int) -> Optional[object]:
    """Validate and get or create user."""
    user_created = await create_user_if_not_exists(user_id)
    if user_created:
        logger.info(f"Created new user: {user_id}")
    return await get_user(user_id)


def _is_file_size_valid(file_size: int, user: object) -> bool:
    """Check if file size is within user's allowed limit."""
    max_size = user.remaining_download_size * 1024 * 1024
    return file_size <= max_size


async def _send_file_size_error_message(
    message: Message, document: object, user: object
) -> None:
    """Send file size limit exceeded message."""
    size_gb = document.file_size / (1024 * 1024 * 1024)
    await message.reply_text(
        f"📏 **File Too Large**\n"
        f"Your file ({size_gb:.1f}GB) exceeds the {user.remaining_download_size}MB limit.\n"
        "💡 Upgrade to a premium account for larger uploads!\n"
        "Use the **/premium** command for details."
    )


async def _send_concurrent_limit_message(message: Message) -> None:
    """Send concurrent downloads limit message."""
    await message.reply_text(
        f"🚦 **Server Busy**\n"
        f"Too many downloads are in progress (limit: {MAX_CONCURRENT_DOWNLOADS}).\n"
        "Please try again in a moment! 🔄"
    )


def _can_process_download() -> bool:
    """Check if new download can be processed."""
    global concurrent_downloads
    if concurrent_downloads >= MAX_CONCURRENT_DOWNLOADS:
        return False
    concurrent_downloads += 1
    return True


async def _process_file(
    client: Client, message: Message, document: object, user: object
) -> None:
    """Process file download and storage."""
    global concurrent_downloads
    size_mb = document.file_size / (1024 * 1024)

    try:
        # Send initial progress message
        progress_msg = await message.reply_text(
            f"📥 **Downloading File**\n"
            f"📄 **Name**: {document.file_name}\n"
            f"📏 **Size**: {size_mb:.2f} MB\n"
            "⏳ Please wait while we process your file..."
        )

        # Download and save file
        temp_file_path = await _download_file(client, message, document)
        try:
            await progress_msg.edit_text(
                f"💾 **Saving File**\n"
                f"📄 **Name**: {document.file_name}\n"
                f"📏 **Size**: {size_mb:.2f} MB\n"
                "⏳ Saving to storage..."
            )

            saved_file = await save_file_to_db(
                user,
                document.file_name,
                temp_file_path,
                document.file_size,
                document.mime_type,
            )

            # Update user storage and send success message
            await _finalize_upload(
                message, progress_msg, saved_file, user, document, size_mb
            )

        finally:
            _cleanup_temp_file(temp_file_path)

    except Exception as e:
        await progress_msg.edit_text(
            f"❌ **Upload Failed**\n"
            f"📄 **Name**: {document.file_name}\n"
            f"📏 **Size**: {size_mb:.2f} MB\n"
            "😔 Something went wrong during processing."
        )
        raise FileProcessingError(str(e))
    finally:
        concurrent_downloads -= 1


async def _download_file(client: Client, message: Message, document: object) -> str:
    """Download file to temporary location."""
    temp_dir = Path(BASE_DIR) / "data" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile(dir=temp_dir, delete=False) as temp_file:
        temp_file_path = temp_file.name
        try:
            logger.info(
                f"Downloading file: {document.file_name}, ID: {document.file_id}"
            )
            await client.download_media(message, file_name=temp_file_path)
            logger.info(f"File downloaded to: {temp_file_path}")
            return temp_file_path
        except Exception as e:
            logger.error(f"Download failed for {document.file_name}: {str(e)}")
            _cleanup_temp_file(temp_file_path)
            raise FileProcessingError(f"Download failed: {str(e)}")


def _cleanup_temp_file(file_path: str) -> None:
    """Clean up temporary file."""
    try:
        os.unlink(file_path)
        logger.info(f"Temporary file cleaned up: {file_path}")
    except OSError as e:
        logger.warning(f"Failed to clean up temporary file {file_path}: {e}")


async def _finalize_upload(
    message: Message,
    progress_msg: Message,
    saved_file: object,
    user: object,
    document: object,
    size_mb: float,
) -> None:
    """Finalize upload process and send success message."""
    full_url = saved_file.file.url
    parsed_url = urlsplit(full_url)
    relative_path = parsed_url.path.lstrip("/") + "?" + parsed_url.query

    user.remaining_download_size -= size_mb
    await sync_to_async(user.save)(update_fields=["remaining_download_size"])

    await progress_msg.edit_text(
        f"🎉 **Upload Successful!**\n"
        f"📄 **Name**: {document.file_name}\n"
        f"📏 **Size**: {size_mb:.2f} MB\n"
        f"🔗 **URL**: {MINIO_BASE_URL}/{relative_path}\n"
        f"💾 **Remaining Storage**: {user.remaining_download_size:.2f} MB"
    )
    logger.info(
        f"File {document.file_name} saved successfully for user {message.from_user.id}"
    )
