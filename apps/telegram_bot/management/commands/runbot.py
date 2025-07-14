import asyncio
from django.core.management.base import BaseCommand
from django.utils import autoreload

from apps.telegram_bot.bot import start_local_bot_async


class Command(BaseCommand):
    help = "Run the Telegram bot with Local Bot API Server (supports files up to 2GB)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reload",
            action="store_true",
            help="Enable auto-reload when code changes (development mode)",
        )

    def handle(self, *args, **kwargs):
        reload_enabled = kwargs.get("reload", False)

        if reload_enabled:
            self.stdout.write(
                self.style.SUCCESS("Starting bot with auto-reload enabled...")
            )
            # Use Django's autoreload mechanism
            autoreload.run_with_reloader(self.run_bot)
        else:
            self.stdout.write(
                self.style.SUCCESS("Starting bot with Local Bot API Server...")
            )
            self.run_bot()

    def run_bot(self):
        """Run the bot - separated for autoreload compatibility"""
        try:
            # Run the async bot function in an event loop
            asyncio.run(start_local_bot_async())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Bot stopped by user"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
