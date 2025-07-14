from django.core.management.base import BaseCommand

from apps.telegram_bot.bot import start_local_bot


class Command(BaseCommand):
    help = "Run the Telegram bot with Local Bot API Server (supports files up to 2GB)"

    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.SUCCESS("Starting bot with Local Bot API Server...")
        )
        try:
            start_local_bot()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Bot stopped by user"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
