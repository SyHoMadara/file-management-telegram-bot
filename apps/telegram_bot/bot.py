import logging
import os
import tempfile
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from asgiref.sync import sync_to_async
from django.core.files import File
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from apps.account.models import User
from apps.file_manager.models import FileManager
from config.settings import BASE_DIR

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_API_TOKEN", "")
API_SERVER = os.environ.get("TELEGRAM_API_SERVER", "")
base_minio_url = "http://" + os.environ.get("MINIO_EXTERNAL_ENDPOINT", "")

logger = logging.getLogger(__name__)

# Rate limiting setup - Adjust these for production
user_request_times = defaultdict(deque)
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("BOT_MAX_REQUESTS_PER_MINUTE", "5"))
CONCURRENT_DOWNLOADS = 0
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("BOT_MAX_CONCURRENT_DOWNLOADS", "3"))


def is_rate_limited(user_id):
    """Check if user is rate limited"""
    now = datetime.now()
    user_times = user_request_times[user_id]

    # Remove old requests (older than 1 minute)
    while user_times and user_times[0] < now - timedelta(minutes=1):
        user_times.popleft()

    # Check if user exceeded limit
    if len(user_times) >= MAX_REQUESTS_PER_MINUTE:
        return True

    # Add current request
    user_times.append(now)
    return False


@sync_to_async
def create_user_if_not_exists(user_id):
    """Create user if not exists - async wrapper"""
    try:
        if not User.objects.filter(username=user_id).exists():
            User.objects.create(username=user_id)
            return True
        return False
    except Exception as e:
        logger.error(f"Error creating user {user_id}: {e}")
        raise


@sync_to_async
def get_user(user_id):
    """Get user by ID - async wrapper"""
    try:
        return User.objects.get(username=user_id)
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        raise


@sync_to_async
def save_file_to_db(user, file_name, temp_file_path, file_size, mime_type):
    """Save file to database using sync_to_async"""
    try:
        with open(temp_file_path, "rb") as temp_file:
            return FileManager.objects.create(
                user=user,
                name=file_name,
                file=File(temp_file, name=file_name),
                file_size=file_size,
                file_mime_type=mime_type or "application/octet-stream",
            )
    except Exception as e:
        logger.error(f"Error saving file {file_name} to database: {e}")
        raise


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads with Local Bot API Server (supports up to 2GB)"""
    global CONCURRENT_DOWNLOADS

    user_id = update.effective_user.id

    # Check rate limit
    if is_rate_limited(user_id):
        await update.message.reply_text(
            "⚠️ Rate limit exceeded!\n"
            f"📊 You can upload max {MAX_REQUESTS_PER_MINUTE} files per minute.\n"
            "⏳ Please wait before sending another file."
        )
        return

    try:
        document = update.message.document

        # Create user if not exists
        user_created = await create_user_if_not_exists(user_id)
        if user_created:
            logger.info(f"Created new user: {user_id}")

        # Check file size
        file_size = document.file_size
        max_size = 2 * 1024 * 1024 * 1024  # 2GB limit for Local Bot API

        # Log file details for debugging
        logger.info(
            f"Processing file: {document.file_name}, Size: {file_size} bytes ({file_size / (1024 * 1024):.2f} MB)"
        )

        if file_size > max_size:
            size_gb = file_size / (1024 * 1024 * 1024)
            await update.message.reply_text(
                f"❌ File too large ({size_gb:.1f}GB). Maximum file size is 2GB."
            )
            return

        # Check if file might be too big for standard Bot API (20MB)
        standard_limit = 20 * 1024 * 1024  # 20MB
        if file_size > standard_limit:
            logger.warning(
                f"File {document.file_name} ({file_size / (1024 * 1024):.2f}MB) exceeds standard Bot API limit (20MB). Requires Local Bot API Server."
            )

        # Send progress message
        size_mb = file_size / (1024 * 1024)
        progress_msg = await update.message.reply_text(
            f"📥 Downloading file...\n"
            f"📁 Name: {document.file_name}\n"
            f"📊 Size: {size_mb:.2f} MB\n"
            f"⏳ Please wait..."
        )

        # Check concurrent download limit
        if CONCURRENT_DOWNLOADS >= MAX_CONCURRENT_DOWNLOADS:
            await update.message.reply_text(
                "⏳ Server busy! Too many downloads in progress.\n"
                f"📊 Current limit: {MAX_CONCURRENT_DOWNLOADS} concurrent downloads\n"
                "🔄 Please try again in a moment."
            )
            return
        # TODO add celery for downloads
        CONCURRENT_DOWNLOADS += 1
        try:
            # Get file from Local Bot API Server
            try:
                file = await context.bot.get_file(document.file_id)
                logger.info(
                    f"File info received: path={file.file_path}, size={file.file_size}"
                )
            except Exception as e:
                if "File is too big" in str(e):
                    await progress_msg.edit_text(
                        f"❌ File download failed!\n"
                        f"📁 Name: {document.file_name}\n"
                        f"📊 Size: {size_mb:.2f} MB\n\n"
                        f"🚨 Error: File too big for current API configuration\n\n"
                        f"💡 Troubleshooting:\n"
                        f"1. Check if Local Bot API Server is running:\n"
                        f"   `docker-compose -f docker-compose-bot.yml ps`\n"
                        f"2. Check API server logs:\n"
                        f"   `docker-compose -f docker-compose-bot.yml logs telegram-bot-api`\n"
                        f"3. Verify API credentials in .env:\n"
                        f"   - TELEGRAM_API_ID\n"
                        f"   - TELEGRAM_API_HASH\n"
                        f"4. Standard Bot API limit: 20MB\n"
                        f"   Local Bot API limit: 2GB\n\n"
                        f"� Current API Server: {API_SERVER}"
                    )
                    logger.error(
                        f"File too big error for {document.file_name} ({size_mb:.2f}MB)."
                    )
                    logger.error(
                        "This suggests Local Bot API Server is not working properly."
                    )
                    logger.error(f"API Server: {API_SERVER}")
                    logger.error(f"File size: {file_size} bytes ({size_mb:.2f} MB)")
                    return
                elif "Not Found" in str(e) or "InvalidToken" in str(e):
                    await progress_msg.edit_text(
                        f"❌ File access failed!\n"
                        f"📁 Name: {document.file_name}\n"
                        f"📊 Size: {size_mb:.2f} MB\n\n"
                        f"🚨 Error: Local Bot API Server configuration issue\n\n"
                        f"💡 Common causes:\n"
                        f"1. Local Bot API Server not running properly\n"
                        f"2. Invalid TELEGRAM_API_ID or TELEGRAM_API_HASH\n"
                        f"3. Bot token not registered with Local API Server\n"
                        f"4. Network connectivity issues\n\n"
                        f"🔧 Quick fixes:\n"
                        f"• Restart Local Bot API Server\n"
                        f"• Verify .env credentials are correct\n"
                        f"• Check docker-compose logs\n\n"
                        f"📝 API Server: {API_SERVER}\n"
                        f"📝 Error: {str(e)}"
                    )
                    logger.error(
                        f"File access error for {document.file_name}: {str(e)}"
                    )
                    logger.error(f"API Server: {API_SERVER}")
                    logger.error(f"File ID: {document.file_id}")
                    logger.error(
                        "Possible causes: Local Bot API Server not running or misconfigured"
                    )
                    return
                else:
                    raise e

            # Create temporary file for streaming download
            temp_dir = Path(BASE_DIR) / "data" / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as temp_file:
                temp_file_path = temp_file.name

                # Download file directly to disk (streaming)
                try:
                    # Use the telegram library's built-in download method
                    # This handles Local Bot API Server automatically
                    logger.info(f"Downloading file using telegram library method")
                    logger.info(
                        f"File path: {file.file_path}, File size: {file.file_size}"
                    )

                    # Download the file directly to the temp location
                    await file.download_to_drive(temp_file_path)

                    logger.info(
                        f"File downloaded to temporary location: {temp_file_path}"
                    )

                except Exception as download_error:
                    logger.error(
                        f"Download failed for {document.file_name}: {str(download_error)}"
                    )
                    logger.error(
                        "This might indicate Local Bot API Server issues or file access problems"
                    )
                    await progress_msg.edit_text(
                        f"❌ File download failed!\n"
                        f"📁 Name: {document.file_name}\n"
                        f"📊 Size: {size_mb:.2f} MB\n\n"
                        f"🚨 Error: {str(download_error)}\n\n"
                        f"💡 Possible causes:\n"
                        f"• Local Bot API Server not properly configured\n"
                        f"• File too large for current setup\n"
                        f"• Network connectivity issues\n\n"
                        f"🔧 Check logs:\n"
                        f"`docker-compose -f docker-compose-bot.yml logs telegram-bot-api`"
                    )
                    # Clean up the temp file if it was created
                    try:
                        os.unlink(temp_file_path)
                    except Exception:
                        pass
                    return

            # Update progress
            await progress_msg.edit_text(
                f"💾 Saving to storage...\n"
                f"📁 Name: {document.file_name}\n"
                f"📊 Size: {size_mb:.2f} MB"
            )

            # Save to database using file path (no memory loading)
            user = await get_user(user_id)

            try:
                saved_file = await save_file_to_db(
                    user,
                    document.file_name,
                    temp_file_path,
                    file_size,
                    document.mime_type,
                )
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Temporary file cleaned up: {temp_file_path}")
                except OSError as e:
                    logger.warning(
                        f"Failed to clean up temporary file {temp_file_path}: {e}"
                    )

            # Generate URL
            full_url = saved_file.file.url
            parsed_url = urlsplit(full_url)
            relative_path = parsed_url.path.lstrip("/") + "?" + parsed_url.query

            # Update with success message
            await progress_msg.edit_text(
                f"✅ File saved successfully!\n"
                f"📁 Name: {document.file_name}\n"
                f"📊 Size: {size_mb:.2f} MB\n"
                f"🔗 URL: {base_minio_url}/{relative_path}"
            )

            logger.info(
                f"File {document.file_name} saved successfully for user {user_id}"
            )

        except Exception as e:
            logger.error(
                f"Error saving file for user {update.effective_user.id}: {str(e)}",
                exc_info=True,
            )
            await update.message.reply_text(f"❌ Error saving file: {str(e)}")

    finally:
        CONCURRENT_DOWNLOADS -= 1


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "🤖 Large File Storage Bot!\n\n"
        "📁 Send me any file up to 2GB and I'll store it.\n\n"
        "💡 Features:\n"
        "• Files up to 2GB (2048MB)\n"
        "• Fast downloads via local server\n"
        "• Direct storage to MinIO\n\n"
        "⚠️ Rate Limits:\n"
        f"• Max {MAX_REQUESTS_PER_MINUTE} files per minute per user\n"
        f"• Max {MAX_CONCURRENT_DOWNLOADS} downloads at once\n\n"
        "Just send a file to get started! 📤"
    )


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
    logger.info(
        f"⚡ Rate limits: {MAX_REQUESTS_PER_MINUTE} files/min per user, {MAX_CONCURRENT_DOWNLOADS} concurrent downloads"
    )

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
    application.add_handler(CommandHandler("start", start_command))
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
