import os
import logging
import telebot
from django.core.files.base import ContentFile
from dotenv import load_dotenv

from apps.account.models import User
from apps.file_manager.models import FileManager
from config.settings import BASE_DIR

load_dotenv(BASE_DIR / ".env")
API_TOKEN = os.environ.get("TELEGRAM_BOT_API_TOKEN", "")

bot = telebot.TeleBot(API_TOKEN)
logger = logging.getLogger(__name__)

base_minio_url = "http://91.99.172.197:8880/minio"

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
        # file.url = http://minio:9000/media/files/LICENSE_omybGFC?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=O9JK85WERINQT88RV3MC%2F20250713%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250713T194534Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=d2466bb87b338cbbabe3554d410335633982574cdfe4597ba9f4d7dd8370907d
        bot.reply_to(message, f"File {str(saved_file.file.name)} saved successfully!")
        logger.info(f"File {file_name} saved successfully for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving file for user {message.from_user.id}: {str(e)}", exc_info=True)
        bot.reply_to(message, f"Error saving file: {str(e)}")


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Send me me a file, and I'll store it for you!")


def start_bot_polling():
    if API_TOKEN is None or API_TOKEN == "":
        raise ValueError("TELEGRAM_BOT_API_TOKEN is not set.")
    bot.polling(none_stop=True)
