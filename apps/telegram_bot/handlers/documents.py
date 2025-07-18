import logging
import os
from collections import defaultdict, deque
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional, Dict
from urllib.parse import urlsplit
import uuid
import asyncio

from asgiref.sync import sync_to_async
from pyrogram.client import Client
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from apps.file_manager.models import FileManager
from apps.telegram_bot.utils.utils import (
    create_user_if_not_exists,
    get_user,
    is_rate_limited,
    save_file_to_db,
)
from tasks import download_file_to_temp_task, save_file_to_db_task

from apps.account.models import User
from config.settings import BASE_DIR

logger = logging.getLogger(__name__)

MINIO_BASE_URL = f"http://{os.environ.get('MINIO_EXTERNAL_ENDPOINT', '')}"
class FileException(Exception):
    pass
class FileSizeExeption(FileException):
    pass
class FileExecption(FileException):
    pass
class DownloadException(Exception):
    pass
class SaveFileException(FileException):
    pass
class FileTempException(FileException):
    pass

class File:
    def __init__(self, document, user: User, download_message: Message, user_message: Message):
        self.file_name = document.file_name 
        self.file_size = document.file_size / (1024 * 1024) # Convert size to MB
        self.file_id = document.file_id
        self.user = user
        self.document = document
        self.user_message = user_message
        self.download_message = download_message
        self.id = str(uuid.uuid4())[:8]  # Unique identifier for the file instance

    def __str__(self):
        return f"FileProperties(file_name={self.file_name}, file_size={self.file_size}, file_id={self.file_id})"

file_set = dict()
async def handle_document(client: Client, message: Message):
    
    user_id = message.from_user.id
    await create_user_if_not_exists(user_id)
    user = await get_user(user_id)
    document = message.document
    download_message = await message.reply_text("about to download", quote=True)
    file_properties = File(document, user, download_message, message)
    file_set[file_properties.id] = file_properties
    try:
        # check limitaion for user
        await _is_size_valid(file_properties)

        # show file propertise and button for download
        await _process_file(file_properties)
    except FileSizeExeption as e:
        logger.error(
            f"File size error for user {user.username}: {str(e)}"
        )
        await download_message.edit_text(
    "File size exceeds user's remaining download size."
            f" You have {user.remaining_download_size} bytes remaining."
        )
    
    except FileExecption as e:
        logger.error(
        f"Error processing file {document.file_name} for user {user.username}: {str(e)}"
        )

async def _is_size_valid(file_properties: File):
    file_size = file_properties.file_size
    user = file_properties.user
    remaining_size = user.remaining_download_size
    if file_size >= remaining_size:
        await file_properties.download_message.edit_text(
            f"file size is {file_size} and you have {remaining_size}\n"
            f"you can upgrade your accout to premium to get up to 5GB download per day\n"
            f"use /premiume command for this :))."
        )
        logger.error(
            f"File size: {file_size}, User: {user.username}, Remaning: {remaining_size}"
        )
        raise FileSizeExeption("File size exceeds user's remaining download size.")


async def _process_file(file_properties: File):
    # show glass file properties  
    file_name = file_properties.file_name
    file_size = file_properties.file_size
    remaining_size = file_properties.user.remaining_download_size
    
    message_text = (
        f"File Name: {file_name}\n"
        f"File Size: {file_size} bytes\n"
        f"Remaining Download Size: {remaining_size} bytes\n"
        "Click the button below to download the file."
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Download File",
                    callback_data=f"download_file_{file_properties.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "Cancel",
                    callback_data="cancel_download"
                )
            ]
        ]
    )

    await file_properties.download_message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

async def handle_download_callback(client: Client, callback_query):
    data = callback_query.data
    if data.startswith("download_file_"):
        file_id = data.split("_")[-1]
        file_properties = file_set.pop(file_id, 0)
        await _download_file(client, file_properties)
        await callback_query.answer("Download started.", show_alert=True)
    elif data == "cancel_download":
        await callback_query.answer("Download cancelled.", show_alert=True)

async def _download_file(client, file_properties: File):
    await file_properties.download_message.edit_text(
            f"File Name: {file_properties.file_name}\n"
            f"File Size: {file_properties.file_size}MB\n"
            "Downloading file..."
    )
    temp_file = None
    try:
        temp_file = await _create_temp_file()
        
        await _download_file_to_temp(client, file_properties, temp_file)

        file_saved = await _save_file_to_db(file_properties, temp_file)

        await _finalize_download(file_properties, file_saved)  

    except DownloadException as e:
        logger.error(f"Error downloading file {file_properties.file_name}: {str(e)}")
        await file_properties.download_message.edit_text(
            "Error downloading file"
        )
    except SaveFileException as e:
        logger.error(f"Error saving file {file_properties.file_name}: {str(e)}")
        await file_properties.download_message.edit_text(
            "Error saving file"
        )
    except FileTempException as e:
        logger.error(f"Error with temporary file for {file_properties.file_name}: {str(e)}")
        await file_properties.download_message.edit_text(
            "Error saving file"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        await file_properties.download_message.edit_text(
            "An unexpected error occurred."
        )
    finally:
        if temp_file:
            await _clear_temp_file(temp_file)

async def _create_temp_file():
    try:
        os.makedirs(BASE_DIR/"data"/"temp", exist_ok=True)
        temp_file = NamedTemporaryFile(dir=BASE_DIR/"data"/"temp" ,delete=False)
        return temp_file
    except Exception as e:
        logger.error(f"Error creating temporary file: {str(e)}")
        raise FileTempException("Failed to create temporary file.") 

async def _download_file_to_temp(client: Client, file_properties: File, temp_file):
    try:
        await client.download_media(file_properties.user_message, file_name=temp_file.name)
        logger.info(f"{file_properties.file_name} downloaded successfully to {temp_file.name}")
        return temp_file.name
    except DownloadException as e:
        logger.error(f"Error downloading file {file_properties.file_name}: {str(e)}")
        raise e

async def _save_file_to_db(file_properties: File, tempfile):
    try:
        saved_file = save_file_to_db_task.delay(
            file_properties=file_properties,
            temp_file_path=tempfile
        )
        while not saved_file.ready():
            await asyncio.sleep(1)
        saved_file = saved_file.get()
        logger.info(f"File {file_properties.file_name} saved to database with ID {saved_file.id}")
        return saved_file
    except SaveFileException as e:
        logger.error(f"Error saving file {file_properties.file_name} to database: {str(e)}")
        raise e

async def _finalize_download(file_properties: File, saved_file: FileManager):
    try:
        file_properties.user.remaining_download_size -= file_properties.file_size
        await sync_to_async(file_properties.user.save)(update_fields=['remaining_download_size'])
        full_url = saved_file.file.url
        parsed_url = urlsplit(full_url)
        relative_path = parsed_url.path.lstrip("/") + "?" + parsed_url.query
        logger.info(f"File {file_properties.file_name} downloaded successfully. Remaining size: {file_properties.user.remaining_download_size}MB")
        await file_properties.download_message.edit_text(
            f"File {file_properties.file_name} downloaded successfully!\n"
            f"File Size: {file_properties.file_size}MB\n"
            f"Remaining Download Size: {file_properties.user.remaining_download_size} bytes\n"
            f"\n\nYou can download it from here: [Download File]({MINIO_BASE_URL}/{relative_path})",
        )
    except Exception as e:
        logger.error(f"Error finalizing download for {file_properties.file_name}: {str(e)}")
        await file_properties.download_message.edit_text(
            "Error finalizing download."
        )

async def _clear_temp_file(temp_file):
    try:
        if temp_file and os.path.exists(temp_file.name):
            os.remove(temp_file.name)
            logger.info(f"Temporary file {temp_file.name} cleared successfully.")
    except Exception as e:
        logger.error(f"Error clearing temporary file {temp_file.name}: {str(e)}")
        raise FileTempException("Failed to clear temporary file.")
