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
        self, document, user: User, download_message: Message, user_message: Message
    ):
        self.file_name = document.file_name
        self.file_size = document.file_size / (1024 * 1024)  # Convert size to MB
        self.file_id = document.file_id
        self.user = user
        self.document = document
        self.user_message = user_message
        self.download_message = download_message
        self.id = str(uuid.uuid4())[:8]  # Unique identifier for the file instance

    def __str__(self):
        return f"FileProperties(file_name={self.file_name}, file_size={self.file_size}, file_id={self.file_id})"
