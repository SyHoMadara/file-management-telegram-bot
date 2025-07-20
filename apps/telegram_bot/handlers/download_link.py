import asyncio
import logging
import os
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit
import yt_dlp

from asgiref.sync import sync_to_async
from pyrogram.client import Client
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from apps.file_manager.models import FileManager
from apps.telegram_bot.models import (
    DownloadException,
    File,
    FileException,
    FileSizeExeption,
    FileTempException,
    SaveFileException,
)
from apps.telegram_bot.utils.utils import create_user_if_not_exists, get_user, save_file_to_db
from config.settings import BASE_DIR, MINIO_URL_EXPIRY_HOURS

logger = logging.getLogger(__name__)

MINIO_BASE_URL = f"http://{os.environ.get('MINIO_EXTERNAL_ENDPOINT', '')}"
video_download_set = dict()


class VideoLinkException(FileException):
    pass


class VideoInfoException(VideoLinkException):
    pass


class UnsupportedURLException(VideoLinkException):
    pass


async def handle_video_link(client: Client, message: Message):
    """Main handler for video download links"""
    user_id = message.from_user.id
    logger.info(f"Processing video link request from user {user_id}")
    
    await create_user_if_not_exists(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )
    user = await get_user(user_id)
    url = message.text.strip()
    
    logger.info(f"User {user.username} requested video download from URL: {url[:50]}...")

    download_message = await message.reply_text("🔍 Analyzing video...", quote=True)
    
    try:
        video_info = await _get_video_info(url)
        logger.info(f"Successfully extracted video info for user {user.username}: {video_info.get('title', 'Unknown')}")
        await _process_video_info(client, message, user, download_message, url, video_info)
    except VideoInfoException as e:
        logger.error(f"Video info error for user {user.username}: {str(e)}")
        await download_message.edit_text(
            "❌ <b>Failed to analyze video</b>\n\n"
            "This might happen if:\n"
            "• The video is private or restricted\n"
            "• The URL is invalid or not supported\n"
            "• The platform is temporarily unavailable\n\n"
            "Please try again or use a different URL.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Unexpected error for user {user.username}: {str(e)}")
        await download_message.edit_text("❌ An unexpected error occurred while processing the video.")


async def _get_video_info(url: str) -> dict:
    """Extract video information using yt-dlp"""
    logger.info(f"Extracting video info from URL: {url[:50]}...")
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        def extract_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        # Run yt-dlp in a thread to avoid blocking
        info = await asyncio.get_event_loop().run_in_executor(None, extract_info)
        logger.info(f"Video info extracted successfully. Title: {info.get('title', 'Unknown')}")
        return info
    except Exception as e:
        logger.error(f"Error extracting video info from {url[:50]}...: {str(e)}")
        raise VideoInfoException("Failed to extract video information.")


async def _process_video_info(client: Client, message: Message, user, download_message: Message, url: str, video_info: dict):
    """Process video information and show quality options"""
    try:
        title = video_info.get('title', 'Unknown Title')
        uploader = video_info.get('uploader', 'Unknown')
        duration = video_info.get('duration', 0)
        
        logger.info(f"Processing video: {title} by {uploader} (Duration: {duration}s)")
        
        # Format duration
        duration_str = _format_duration(duration) if duration else "Unknown"
        
        # Get available formats
        formats = _get_available_formats(video_info)
        logger.info(f"Found {len(formats)} available video formats")
        
        if not formats:
            logger.warning(f"No downloadable formats found for video: {title}")
            await download_message.edit_text(
                "❌ <b>No downloadable formats found</b>\n\n"
                "This video might not be available for download.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Create video properties object
        video_properties = File(
            user=user,
            download_message=download_message,
            user_message=message,
            file_name=f"{title}.%(ext)s",  # Will be formatted later
            extra_data={
                'url': url,
                'video_info': video_info,
                'formats': formats,
                'title': title,
                'uploader': uploader,
                'duration': duration
            },
            document=None,  # No document for video links
            file_size=0  # Will be updated after download
        )
        
        video_download_set[video_properties.id] = video_properties
        logger.info(f"Created video download session for: {title}")
        
        # Create quality selection keyboard
        keyboard = _create_quality_keyboard(formats, video_properties.id)
        
        message_text = (
            f"🎬 <b>{title}</b>\n"
            f"👤 <b>Channel:</b> {uploader}\n"
            f"⏱️ <b>Duration:</b> {duration_str}\n"
            f"🗃️ <b>Your Quota:</b> {user.remaining_download_size:.2f}MB\n\n"
            "📋 <b>Available Qualities:</b>\n"
            "Select the quality you want to download:"
        )
        
        await download_message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"Quality selection displayed for: {title}")
        
    except Exception as e:
        logger.error(f"Error processing video info: {str(e)}")
        await download_message.edit_text("❌ Error processing video information.")


def _format_duration(seconds: int) -> str:
    """Format duration from seconds to readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def _get_available_formats(video_info: dict) -> list:
    """Extract and filter available video formats"""
    formats = video_info.get('formats', [])
    if not formats:
        logger.warning("No formats found in video info")
        return []
    
    logger.info(f"Processing {len(formats)} total formats from video info")
    
    # Filter and sort formats
    video_formats = []
    seen_qualities = set()
    
    for fmt in formats:
        if not fmt.get('vcodec') or fmt.get('vcodec') == 'none':
            continue  # Skip audio-only formats
            
        height = fmt.get('height', 0)
        filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
        ext = fmt.get('ext', 'mp4')
        format_id = fmt.get('format_id', '')
        
        if height and height > 0:
            quality_label = f"{height}p"
            if quality_label not in seen_qualities:
                seen_qualities.add(quality_label)
                video_formats.append({
                    'format_id': format_id,
                    'quality': quality_label,
                    'height': height,
                    'filesize': filesize,
                    'ext': ext,
                    'filesize_mb': (filesize / (1024 * 1024)) if filesize else 0
                })
    
    # Sort by quality (height) descending
    video_formats.sort(key=lambda x: x['height'], reverse=True)
    
    # Limit to top 8 qualities to avoid inline keyboard limits
    final_formats = video_formats[:8]
    
    return final_formats


def _create_quality_keyboard(formats: list, video_id: str) -> InlineKeyboardMarkup:
    """Create inline keyboard with quality options"""
    buttons = []
    
    for fmt in formats:
        quality = fmt['quality']
        size_text = f" (~{fmt['filesize_mb']:.0f}MB)" if fmt['filesize_mb'] > 0 else ""
        button_text = f"📹 {quality}{size_text}"
        callback_data = f"download_video_{video_id}_{fmt['format_id']}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Add audio-only option
    audio_callback = f"download_audio_{video_id}"
    buttons.append([InlineKeyboardButton("🎵 Audio Only (Best Quality)", callback_data=audio_callback)])
    
    # Add cancel button
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_video_download")])
    
    return InlineKeyboardMarkup(buttons)


async def handle_video_download_callback(client: Client, callback_query):
    """Handle quality selection callback"""
    data = callback_query.data
    user_id = callback_query.from_user.id
    logger.info(f"Received video download callback: '{data}' from user {user_id}")
    
    try:
        if data.startswith("download_video_"):
            parts = data.split("_")
            if len(parts) < 4:
                logger.error(f"Invalid callback data format: {data}")
                await callback_query.answer("❌ Invalid request format.", show_alert=True)
                return
                
            video_id = parts[2]
            format_id = parts[3]
            
            video_properties = video_download_set.get(video_id)
            if not video_properties:
                logger.warning(f"Video session expired for ID: {video_id}")
                await callback_query.answer("❌ Video session expired. Please try again.", show_alert=True)
                return
                
            logger.info(f"Starting video download for user {video_properties.user.username}: format {format_id}")
            await callback_query.answer("⬇️ Download started...", show_alert=True)
            await _download_video(client, video_properties, format_id, is_audio_only=False)
            
        elif data.startswith("download_audio_"):
            parts = data.split("_")
            if len(parts) < 3:
                logger.error(f"Invalid callback data format: {data}")
                await callback_query.answer("❌ Invalid request format.", show_alert=True)
                return
                
            video_id = parts[2]
            
            video_properties = video_download_set.get(video_id)
            if not video_properties:
                logger.warning(f"Video session expired for ID: {video_id}")
                await callback_query.answer("❌ Video session expired. Please try again.", show_alert=True)
                return
                
            logger.info(f"Starting audio download for user {video_properties.user.username}")
            await callback_query.answer("⬇️ Audio download started...", show_alert=True)
            await _download_video(client, video_properties, None, is_audio_only=True)
            
        elif data == "cancel_video_download":
            logger.info(f"Video download cancelled by user {user_id}")
            await callback_query.answer("❌ Download cancelled.", show_alert=True)
            await callback_query.message.edit_text(
                "❌ <b>Download cancelled</b>\n\nYou can send another video URL to try again.",
                parse_mode=ParseMode.HTML
            )
        else:
            logger.warning(f"Unknown callback data received: {data}")
            await callback_query.answer("❌ Unknown action.", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in video download callback handler: {str(e)}")
        await callback_query.answer("❌ An error occurred. Please try again.", show_alert=True)



async def _download_video(client: Client, video_properties: File, format_id: str = None, is_audio_only: bool = False):
    """Download video using yt-dlp"""
    url = video_properties.extra_data['url']
    title = video_properties.extra_data['title']
    
    # Remove video from set to free memory
    video_download_set.pop(video_properties.id, None)
    logger.info(f"Starting {'audio' if is_audio_only else 'video'} download for {title} (format: {format_id})")
    
    await video_properties.download_message.edit_text(
        f"📥 <b>Downloading:</b> {title}\n"
        f"🎬 <b>Quality:</b> {'Audio Only' if is_audio_only else f'Video ({format_id})'}\n"
        f"⏳ Please wait...",
        parse_mode=ParseMode.HTML
    )
    
    temp_file = None
    try:
        temp_file = await _create_temp_file()
        downloaded_file_path = await _download_video_to_temp(url, temp_file, format_id, is_audio_only)
        
        # Get actual file size
        file_size_bytes = os.path.getsize(downloaded_file_path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        logger.info(f"Video downloaded successfully: {downloaded_file_path} ({file_size_mb:.2f}MB)")
        
        # Update video properties with actual file info
        video_properties.file_size = file_size_mb
        video_properties.file_name = os.path.basename(downloaded_file_path)
        
        # Check if size is valid
        await _is_video_size_valid(video_properties)
        
        # Save to database
        mime_type = "audio/mp3" if is_audio_only else "video/mp4"
        file_saved = await _save_video_to_db(video_properties, downloaded_file_path, mime_type)
        await _finalize_video_download(video_properties, file_saved)
        
    except FileSizeExeption as e:
        logger.error(f"File size error for user {video_properties.user.username}: {str(e)}")
        await video_properties.download_message.edit_text(
            f"⚠️ <b>File size exceeds your remaining download limit.</b>\n"
            f"<b>File size:</b> {video_properties.file_size:.2f}MB\n"
            f"<b>Remaining quota:</b> {video_properties.user.remaining_download_size:.2f}MB\n\n"
            "Try selecting a lower quality or upgrade to premium for higher limits.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Unexpected error during video download for user {video_properties.user.username}: {str(e)}")
        await video_properties.download_message.edit_text("❌ An unexpected error occurred during download.")
    finally:
        if temp_file:
            await _clear_temp_file(temp_file)


async def _create_temp_file():
    """Create temporary file for download"""
    try:
        temp_dir = BASE_DIR / "data" / "temp"
        os.makedirs(temp_dir, exist_ok=True)
        return NamedTemporaryFile(dir=temp_dir, delete=False)
    except Exception as e:
        logger.error(f"Temp file creation error: {str(e)}")
        raise FileTempException("Temporary file creation failed.")


async def _download_video_to_temp(url: str, temp_file, format_id: str = None, is_audio_only: bool = False) -> str:
    """Download video to temporary file using yt-dlp"""
    logger.info(f"Starting {'audio' if is_audio_only else 'video'} download - Format: {format_id}")
    
    try:
        # Prepare yt-dlp options
        if is_audio_only:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{temp_file.name}.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '192K',
            }
        else:
            if format_id:
                ydl_opts = {
                    'format': format_id,
                    'outtmpl': f'{temp_file.name}.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                }
            else:
                ydl_opts = {
                    'format': 'best[height<=720]',  # Default to 720p if no format specified
                    'outtmpl': f'{temp_file.name}.%(ext)s',
                    'quiet': True,
                    'no_warnings': True,
                }
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        # Run download in executor to avoid blocking
        await asyncio.get_event_loop().run_in_executor(None, download)
        
        # Close the temp file before searching for downloaded files
        temp_file.close()
        
        # Find the downloaded file (yt-dlp adds extension)
        temp_dir = os.path.dirname(temp_file.name)
        temp_basename = os.path.basename(temp_file.name)
        
        all_files = os.listdir(temp_dir)
        downloaded_files = [f for f in all_files if f.startswith(temp_basename)]
        
        if not downloaded_files:
            logger.error("No file was downloaded by yt-dlp")
            raise DownloadException("No file was downloaded")
            
        downloaded_file_path = os.path.join(temp_dir, downloaded_files[0])
        
        # Validate downloaded file
        if not os.path.exists(downloaded_file_path):
            raise DownloadException("Downloaded file not found")
            
        file_size = os.path.getsize(downloaded_file_path)
        if file_size == 0:
            raise DownloadException("Downloaded file is empty")
        
        logger.info(f"Download completed: {downloaded_file_path} ({file_size / (1024*1024):.2f}MB)")
        return downloaded_file_path
        
    except Exception as e:
        logger.error(f"yt-dlp download error: {str(e)}")
        raise DownloadException(f"Video download failed: {str(e)}")


async def _is_video_size_valid(video_properties: File):
    """Check if video size is within user's quota"""
    file_size = video_properties.file_size
    user = video_properties.user
    remaining_size = user.remaining_download_size

    if file_size >= remaining_size:
        raise FileSizeExeption("File size exceeds user's remaining download size.")


async def _save_video_to_db(video_properties: File, temp_file_path: str, mime_type: str):
    """Save video file to database using FileManager"""
    try:
        result = await save_file_to_db(
            video_properties.user,
            video_properties.file_name,
            temp_file_path,
            video_properties.file_size,
            mime_type,
        )
        return result
    except Exception as e:
        logger.error(f"Database save error for video {video_properties.file_name}: {str(e)}")
        raise SaveFileException("Failed to save video to database.")


async def _finalize_video_download(video_properties: File, saved_file: FileManager):
    """Finalize video download and send download link"""
    try:
        user = video_properties.user
        
        user.remaining_download_size -= video_properties.file_size
        await sync_to_async(user.save)(update_fields=["remaining_download_size"])

        full_url = saved_file.file.url
        parsed_url = urlsplit(full_url)
        relative_path = parsed_url.path.lstrip("/") + "?" + parsed_url.query
        expiry_hours = int(MINIO_URL_EXPIRY_HOURS.total_seconds() // 3600)

        await video_properties.download_message.edit_text(
            f"✅ <b>{video_properties.extra_data['title']}</b> downloaded successfully!\n"
            f"📦 <b>Size:</b> {video_properties.file_size:.2f}MB\n"
            f"🗃️ <b>Remaining Quota:</b> {user.remaining_download_size:.2f}MB\n\n"
            f"<a href='{MINIO_BASE_URL}/{relative_path}'>🔗 Download Link</a>\n\n"
            f"⏳ <i>This link will expire in {expiry_hours} hour(s).</i>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        
        logger.info(f"Download completed: {video_properties.extra_data['title']}")
        
    except Exception as e:
        logger.error(f"Finalize error for user {video_properties.user.username}: {str(e)}")
        await video_properties.download_message.edit_text("❌ Failed to complete the download.")


async def _clear_temp_file(temp_file):
    """Clean up temporary files"""
    try:
        # Remove the temp file and any files with the same base name (yt-dlp creates files with extensions)
        base_path = temp_file.name
        directory = os.path.dirname(base_path)
        base_name = os.path.basename(base_path)
        
        for filename in os.listdir(directory):
            if filename.startswith(base_name):
                file_path = os.path.join(directory, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
    except Exception as e:
        logger.error(f"Error removing temp files: {str(e)}")
        raise FileTempException("Failed to delete temporary files.")