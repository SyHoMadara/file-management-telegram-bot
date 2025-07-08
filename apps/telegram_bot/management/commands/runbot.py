from django.core.management.base import BaseCommand

from apps.telegram_bot.bot import start_bot_polling


class Command(BaseCommand):
    help = "Run the Telegram bot in polling mode"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting bot polling..."))
        start_bot_polling()
