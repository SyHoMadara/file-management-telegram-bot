import asyncio
import logging
import os
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from asgiref.sync import sync_to_async
from pyrogram.client import Client
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from apps.file_manager.models import FileManager
from apps.telegram_bot.models import (
    DownloadException,
    File,
    FileException,
    FileSizeExeption,
    FileTempException,
    SaveFileException,
)
from apps.telegram_bot.utils.utils import create_user_if_not_exists, get_user, save_file_to_db
from config.settings import BASE_DIR

from ..tasks import save_file_to_db_task

logger = logging.getLogger(__name__)

MINIO_BASE_URL = f"http://{os.environ.get('MINIO_EXTERNAL_ENDPOINT', '')}"
file_set = dict()

async def handle_document(client: Client, message: Message):
    user_id = message.from_user.id
    await create_user_if_not_exists(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )
    user = await get_user(user_id)
    document = message.document
    download_message = await message.reply_text("📥 Preparing to download...", quote=True)
    file_properties = File(document, user, download_message, message)
    file_set[file_properties.id] = file_properties

    try:
        await _is_size_valid(file_properties)
        await _process_file(file_properties)
    except FileSizeExeption as e:
        logger.error(f"File size error for user {user.username}: {str(e)}")
        await download_message.edit_text(
            f"⚠️ <b>File size exceeds your remaining download limit.</b>\n"
            f"<b>File size:</b> {file_properties.file_size:.2f}MB\n"
            f"<b>Remaining quota:</b> {user.remaining_download_size:.2f}MB\n\n"
            "Upgrade to premium and get up to 5GB daily download limit.\n"
            "Use /premium command to upgrade. 🚀",
            parse_mode=ParseMode.HTML
        )
    except FileException as e:
        logger.error(f"Error processing file {document.file_name} for user {user.username}: {str(e)}")
        await download_message.edit_text("❌ Error while processing your file.")

async def _is_size_valid(file_properties: File):
    file_size = file_properties.file_size
    user = file_properties.user
    remaining_size = user.remaining_download_size

    if file_size >= remaining_size:
        raise FileSizeExeption("File size exceeds user's remaining download size.")

async def _process_file(file_properties: File):
    file_name = file_properties.file_name
    file_size = file_properties.file_size
    remaining_size = file_properties.user.remaining_download_size

    message_text = (
        f"<b>📄 File:</b> {file_name}\n"
        f"<b>📦 Size:</b> {file_size:.2f}MB\n"
        f"<b>🗃️ Remaining Quota:</b> {remaining_size:.2f}MB\n\n"
        "👇 Click below to download:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Download File", callback_data=f"download_file_{file_properties.id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_download")]
    ])

    await file_properties.download_message.edit_text(
        message_text, reply_markup=keyboard, parse_mode=ParseMode.HTML
    )

async def handle_download_callback(client: Client, callback_query):
    data = callback_query.data
    if data.startswith("download_file_"):
        file_id = data.split("_")[-1]
        file_properties = file_set.pop(file_id, 0)
        await callback_query.answer("⬇️ Download started...", show_alert=True)
        await _download_file(client, file_properties)
    elif data == "cancel_download":
        await callback_query.answer("❌ Download cancelled.", show_alert=True)

async def _download_file(client, file_properties: File):
    await file_properties.download_message.edit_text(
        f"📥 <b>Downloading:</b> {file_properties.file_name}\n"
        f"📦 <b>Size:</b> {file_properties.file_size:.2f}MB",
        parse_mode=ParseMode.HTML
    )

    temp_file = None
    try:
        temp_file = await _create_temp_file()
        await _download_file_to_temp(client, file_properties, temp_file)
        file_saved = await _save_file_to_db(file_properties, temp_file)
        await _finalize_download(file_properties, file_saved)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        await file_properties.download_message.edit_text("❌ An unexpected error occurred.")
    finally:
        if temp_file:
            await _clear_temp_file(temp_file)

async def _create_temp_file():
    try:
        os.makedirs(BASE_DIR / "data" / "temp", exist_ok=True)
        return NamedTemporaryFile(dir=BASE_DIR / "data" / "temp", delete=False)
    except Exception as e:
        logger.error(f"Temp file creation error: {str(e)}")
        raise FileTempException("Temporary file creation failed.")

async def _download_file_to_temp(client: Client, file_properties: File, temp_file):
    try:
        await client.download_media(file_properties.user_message, file_name=temp_file.name)
        logger.info(f"{file_properties.file_name} downloaded to {temp_file.name}")
        return temp_file.name
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise DownloadException("Download failed.")

async def _save_file_to_db(file_properties: File, temp_file):
    try:
        return await save_file_to_db(
            file_properties.user,
            file_properties.file_name,
            temp_file.name,
            file_properties.file_size,
            file_properties.document.mime_type,
        )
    except Exception as e:
        logger.error(f"Database save error: {str(e)}")
        raise SaveFileException("Failed to save file to DB.")

async def _finalize_download(file_properties: File, saved_file: FileManager):
    try:
        user = file_properties.user
        user.remaining_download_size -= file_properties.file_size
        await sync_to_async(user.save)(update_fields=["remaining_download_size"])

        full_url = saved_file.file.url
        parsed_url = urlsplit(full_url)
        relative_path = parsed_url.path.lstrip("/") + "?" + parsed_url.query

        await file_properties.download_message.edit_text(
            f"✅ <b>{file_properties.file_name}</b> downloaded successfully!\n"
            f"📦 <b>Size:</b> {file_properties.file_size:.2f}MB\n"
            f"🗃️ <b>Remaining Quota:</b> {user.remaining_download_size:.2f}MB\n\n"
            f"<a href='{MINIO_BASE_URL}/{relative_path}'>🔗 Download Link</a>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Finalize error: {str(e)}")
        await file_properties.download_message.edit_text("❌ Failed to complete the download.")

async def _clear_temp_file(temp_file):
    try:
        if temp_file and os.path.exists(temp_file.name):
            os.remove(temp_file.name)
            logger.info(f"Temp file {temp_file.name} deleted.")
    except Exception as e:
        logger.error(f"Error removing temp file: {str(e)}")
        raise FileTempException("Failed to delete temporary file.")
