import uuid

from pyrogram.types import Message

from apps.account.models import User


class FileException(Exception):
    pass


class FileSizeExeption(FileException):
    pass


class DownloadException(Exception):
    pass


class SaveFileException(FileException):
    pass


class FileTempException(FileException):
    pass


class File:
    def __init__(
        self, 
        user: User, 
        download_message: Message, 
        user_message: Message,
        # New parameters for video handling
        file_name: str,
        extra_data: dict, 
        document=None,  # Make document optional
        file_size: float = 0
    ):
        if document:
            # Document initialization (original behavior)
            self.file_name = document.file_name
            self.file_size = document.file_size / (1024 * 1024)  # Convert size to MB
            self.file_id = document.file_id
            self.document = document
        else:
            # Video link initialization (new behavior)
            self.file_name = file_name
            self.file_size = file_size
            self.file_id = None
            self.document = None
        
        self.user = user
        self.user_message = user_message
        self.download_message = download_message
        self.id = str(uuid.uuid4())[:8]  # Unique identifier for the file instance
        self.extra_data = extra_data or {}  # Store additional data like URL, formats, etc.

    def __str__(self):
        return f"FileProperties(file_name={self.file_name}, file_size={self.file_size}, file_id={self.file_id})"
