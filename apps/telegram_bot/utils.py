from .tasks import detect_file_type_task, validate_file_task


def _get_file_object(file):
    """Helper function to get the underlying file object from either Django FileField or regular file."""
    try:
        return file.file if hasattr(file, "file") else file
    except AttributeError:
        raise ValueError("Invalid file object provided")


def validate_file_type(file, allowed_mime_types=None, exclude_mime_types=None):
    """Validate file type for both Django FileField and regular file objects.

    Args:
        file: Either a Django FileField/UploadedFile or regular file object
        allowed_mime_types: List of allowed MIME types (optional)
        exclude_mime_types: List of excluded MIME types (optional)

    Returns:
        bool: Result from validate_file_task
    """
    if allowed_mime_types is None:
        allowed_mime_types = []
    if exclude_mime_types is None:
        exclude_mime_types = []

    try:
        file_obj = _get_file_object(file)
        file_pos = file_obj.tell()
        file_content = file_obj.read(2048)
        file_obj.seek(file_pos)

        # Call the Celery task asynchronously
        result = validate_file_task.delay(
            file_content, allowed_mime_types, exclude_mime_types
        )
        return result.get()  # Wait for the task result (synchronous for simplicity)
    except Exception as e:
        raise ValueError(f"Error validating file type: {str(e)}")


def detect_file_type(file):
    """Detect the file type for both Django FileField and regular file objects.

    Args:
        file: Either a Django FileField/UploadedFile or regular file object

    Returns:
        str: Detected MIME type or None if detection fails
    """
    try:
        file_obj = _get_file_object(file)
        file_pos = file_obj.tell()
        file_content = file_obj.read(2048)
        file_obj.seek(file_pos)

        # Call the Celery task asynchronously
        result = detect_file_type_task.delay(file_content)
        return result.get()  # Wait for the task result
    except Exception as e:
        raise ValueError(f"Error detecting file type: {str(e)}")
