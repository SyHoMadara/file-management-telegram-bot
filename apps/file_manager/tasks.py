import magic
from celery import shared_task


def validate_file_type_sync(file_content, allowed_mime_types=None, exclude_mime_types=None):
    """Validate if the file's MIME type is in the allowed list.

    Args:
        file_content: Bytes content of the file (first 2048 bytes)
        allowed_mime_types: List of allowed MIME types (optional)
        exclude_mime_types: List of excluded MIME types (optional)

    Returns:
        bool: True if the file's MIME type is valid, False otherwise
    """
    if not file_content:
        return False

    try:
        mime = magic.from_buffer(file_content, mime=True)
        if allowed_mime_types is None:
            allowed_mime_types = []
        if exclude_mime_types is None:
            exclude_mime_types = []

        if mime in exclude_mime_types:
            return False
        if len(allowed_mime_types) != 0:
            return mime in allowed_mime_types
        return True  # If no allowed_mime_types specified, assume valid unless excluded
    except Exception:
        return False


@shared_task
def validate_file_task(file_content, allowed_mime_types=None, exclude_mime_types=None):
    """Celery task to validate the MIME type of a file against allowed types.

    Args:
        file_content: Bytes content of the file (first 2048 bytes)
        allowed_mime_types: List of allowed MIME types
        exclude_mime_types: List of excluded MIME types

    Returns:
        bool: True if the file's MIME type is valid, False otherwise
    """
    return validate_file_type_sync(file_content, allowed_mime_types, exclude_mime_types)


@shared_task
def detect_file_type_task(file_content):
    """Celery task to detect the MIME type of a file.

    Args:
        file_content: Bytes content of the file (first 2048 bytes)

    Returns:
        str: Detected MIME type or None if detection fails
    """
    if not file_content:
        return None
    try:
        return magic.from_buffer(file_content, mime=True)
    except Exception:
        return None