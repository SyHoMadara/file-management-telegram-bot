import logging
import os

from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from apps.telegram_bot.handlers.commons import help_command, start_command
from apps.telegram_bot.handlers.documents import handle_document
from config.settings import BASE_DIR

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_API_TOKEN", "")
API_SERVER = os.environ.get("TELEGRAM_API_SERVER", "")
base_minio_url = "http://" + os.environ.get("MINIO_EXTERNAL_ENDPOINT", "")

logger = logging.getLogger(__name__)


async def check_local_api_server():
    """Check if Local Bot API Server is working properly"""
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            # Check if the API server is responding
            test_url = f"{API_SERVER}/bot{BOT_TOKEN}/getMe"
            async with session.get(test_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        logger.info("✅ Local Bot API Server is responding correctly")
                        return True
                    else:
                        logger.warning(
                            f"⚠️ Local Bot API Server responded but with error: {data}"
                        )
                        return False
                else:
                    logger.warning(
                        f"⚠️ Local Bot API Server returned status {response.status}"
                    )
                    return False
    except ImportError:
        logger.warning("⚠️ aiohttp not available, skipping API server check")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to connect to Local Bot API Server: {e}")
        logger.error(f"   Make sure the API server is running at: {API_SERVER}")
        logger.error(
            "   Check your TELEGRAM_API_ID and TELEGRAM_API_HASH configuration"
        )
        return False


async def start_local_bot_async():
    """Start the bot with Local Bot API Server - async version"""
    if not BOT_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_API_TOKEN must be set in .env file")

    if not API_SERVER:
        raise ValueError(
            "❌ TELEGRAM_API_SERVER must be set in .env file\n"
            "   For Docker: TELEGRAM_API_SERVER=http://telegram-bot-api:8081\n"
            "   For Local: TELEGRAM_API_SERVER=http://localhost:8081"
        )

    # Validate configuration
    if not base_minio_url or base_minio_url == "http://":
        raise ValueError("❌ MINIO_EXTERNAL_ENDPOINT must be set in .env file")

    logger.info("🚀 Starting Large File Bot with Local Bot API Server")
    logger.info(f"🤖 Bot token: ...{BOT_TOKEN[-10:]}")
    logger.info(f"🌐 API Server: {API_SERVER}")
    logger.info(f"📦 MinIO URL: {base_minio_url}")
    # todo
    # logger.info(
    #     f"⚡ Rate limits: {MAX_REQUESTS_PER_MINUTE} files/min per user, {MAX_CONCURRENT_DOWNLOADS} concurrent downloads"
    # )

    # Check Local Bot API Server connectivity
    async def check_and_log_api_server():
        logger.info("🔍 Checking Local Bot API Server connectivity...")
        api_check = await check_local_api_server()
        if api_check is False:
            logger.error("❌ Local Bot API Server check failed!")
            logger.error("   Large file downloads (>20MB) may not work properly")
            logger.error("   Standard Bot API limit: 20MB, Local Bot API limit: 2GB")
            logger.error(
                "   Please check your docker-compose setup and API credentials"
            )
        elif api_check is True:
            logger.info(
                "✅ Local Bot API Server is working - large files up to 2GB supported!"
            )
        else:
            logger.info("⚠️ Could not verify Local Bot API Server status")

    # Create bot instance with custom API server
    bot = Bot(token=BOT_TOKEN, base_url=f"{API_SERVER}/bot")

    # Create application
    application = Application.builder().bot(bot).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    # Handle all document messages
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Add post-init hook to check API server
    async def post_init(application):
        await check_and_log_api_server()

    application.post_init = post_init

    logger.info("✅ Bot handlers registered successfully")
    logger.info("🔄 Starting bot polling...")

    # Initialize and start the application
    await application.initialize()
    await application.post_init(application)
    await application.start()

    # Start polling
    await application.updater.start_polling(drop_pending_updates=True)

    # Keep running until stopped
    try:
        # Run forever
        import asyncio

        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopping...")
    finally:
        # Clean shutdown
        await application.stop()
        await application.shutdown()
