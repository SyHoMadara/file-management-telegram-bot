import logging
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta

from asgiref.sync import sync_to_async
from django.core.files import File

from apps.account.models import User
from apps.file_manager.models import FileManager

logger = logging.getLogger(__name__)

# Rate limiting setup - Adjust these for production

MAX_REQUESTS_PER_MINUTE = int(os.environ.get("BOT_MAX_REQUESTS_PER_MINUTE", "5"))
CONCURRENT_DOWNLOADS = 0
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("BOT_MAX_CONCURRENT_DOWNLOADS", "3"))

# Environment variables
base_minio_url = "http://" + os.environ.get("MINIO_EXTERNAL_ENDPOINT", "")

user_request_times = defaultdict(deque)


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
