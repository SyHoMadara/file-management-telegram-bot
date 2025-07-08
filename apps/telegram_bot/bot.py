import os

import telebot
from dotenv import load_dotenv
from telebot import apihelper

from config.settings import BASE_DIR

# Configure proxy
apihelper.proxy = {
    "http": "http://localhost:2080",
    "https": "http://localhost:2080",
}

load_dotenv(BASE_DIR / ".env")
API_TOKEN = os.environ.get("TELEGRAM_BOT_API_TOKEN", "")

bot = telebot.TeleBot(API_TOKEN)


# Handle '/start' and '/help'
@bot.message_handler(commands=["help", "start"])
def send_welcome(message):
    bot.reply_to(
        message,
        """\
Hi there, I am EchoBot.
I am here to echo your kind words back to you. Just say anything nice and I'll say the exact same thing to you!\
""",
    )


# Handle all other messages with content_type 'text' (content_types defaults to ['text'])
@bot.message_handler(func=lambda message: True)
def echo_message(message):
    bot.reply_to(message, message.text)


def start_bot_polling():
    bot.infinity_polling()
