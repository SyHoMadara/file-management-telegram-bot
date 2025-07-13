from django.core.management.base import BaseCommand
from apps.telegram_bot.local_bot import start_local_bot


class Command(BaseCommand):
    help = 'Run the Local Bot API Telegram bot (supports files up to 2GB)'

    def handle(self, *args, **options):
        self.stdout.write('Starting Local Bot API bot...')
        try:
            start_local_bot()
        except KeyboardInterrupt:
            self.stdout.write('Bot stopped by user')
        except Exception as e:
            self.stdout.write(f'Error: {e}')
