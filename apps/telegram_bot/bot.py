import os
import logging
import telebot
from django.core.files.base import ContentFile
from dotenv import load_dotenv
from urllib.parse import urlparse, urlsplit

from apps.account.models import User
from apps.file_manager.models import FileManager
from config.settings import BASE_DIR

load_dotenv(BASE_DIR / ".env")
API_TOKEN = os.environ.get("TELEGRAM_BOT_API_TOKEN", "")

bot = telebot.TeleBot(API_TOKEN)
logger = logging.getLogger(__name__)

base_minio_url = "http://" + os.environ.get("MINIO_EXTERNAL_ENDPOINT", "")

def creat_user_if_not_exists(user_id):
    if not User.objects.filter(username=user_id).exists():
        User.objects.create(username=user_id)


@bot.message_handler(content_types=["document"])
def handle_file(message):
    try:
        creat_user_if_not_exists(message.from_user.id)
        file_info = bot.get_file(message.document.file_id)
        file = bot.download_file(file_info.file_path)
        file_name = message.document.file_name
        user_id = message.from_user.id
        user = User.objects.get(username=user_id)
        saved_file = FileManager.objects.create(
            user=user,
            name=file_name,
            file=ContentFile(file, name=file_name),
            file_size=file_info.file_size,
            file_mime_type=message.document.mime_type,
        )
        full_url = saved_file.file.url
        parsed_url = urlsplit(full_url)
        relative_path = parsed_url.path.lstrip('/') + '?' + parsed_url.query
        bot.reply_to(message, f"File {base_minio_url}/{relative_path} saved successfully!")
        logger.info(f"File {file_name} saved successfully for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving file for user {message.from_user.id}: {str(e)}", exc_info=True)
        bot.reply_to(message, f"Internal server error saving file")


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Send me me a file, and I'll store it for you!")


def start_bot_polling():
    if API_TOKEN is None or API_TOKEN == "":
        raise ValueError("TELEGRAM_BOT_API_TOKEN is not set.")
    bot.polling(none_stop=True)
