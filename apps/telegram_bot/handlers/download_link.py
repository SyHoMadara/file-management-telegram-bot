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
from apps.telegram_bot.utils.utils import (
    create_user_if_not_exists,
    get_user,
    save_file_to_db,
)
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
        error_msg = str(e).lower()
        
        if "sign in" in error_msg or "bot" in error_msg or "cookies" in error_msg:
            await download_message.edit_text(
                "❌ <b>YouTube Bot Detection</b>\n\n"
                "YouTube is currently blocking automated requests. This can happen when:\n"
                "• Too many requests are made in a short time\n"
                "• YouTube's anti-bot measures are active\n\n"
                "🔄 <b>Please try:</b>\n"
                "• Waiting a few minutes before trying again\n"
                "• Using a different video URL\n"
                "• Trying again later when traffic is lower\n\n"
                "💡 <i>This is a temporary YouTube restriction, not a bot issue.</i>",
                parse_mode=ParseMode.HTML
            )
        else:
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
            # Add user agent and other headers to avoid bot detection
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip,deflate',
                'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                'Keep-Alive': '300',
                'Connection': 'keep-alive',
            },
            # Add extractor args for YouTube - use multiple clients for maximum format extraction
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'ios'],  # Try multiple clients
                    'player_skip': [],  # Don't skip any players
                }
            },
            # Force extraction of all available formats
            'format_sort': ['res', 'ext'],  # Sort by resolution and extension
            'listformats': False,  # Don't just list, actually extract info
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
        
        # Try a fallback with simplified options
        try:
            logger.info("Attempting fallback extraction with simplified options...")
            fallback_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android'],  # Android client often works better
                    }
                },
            }
            
            def fallback_extract():
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            info = await asyncio.get_event_loop().run_in_executor(None, fallback_extract)
            logger.info("Fallback extraction successful!")
            return info
        except Exception as fallback_error:
            logger.error(f"Fallback extraction also failed: {str(fallback_error)}")
            raise VideoInfoException("Failed to extract video information. YouTube may be blocking requests.")


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
    """Extract and filter available video formats, prioritizing reliable downloads"""
    formats = video_info.get('formats', [])
    if not formats:
        logger.warning("No formats found in video info")
        return []
    
    logger.info(f"Processing {len(formats)} total formats from video info")
    
    # Debug: Log all formats to understand what we're getting vs CLI
    logger.info("All available formats from yt-dlp:")
    for i, fmt in enumerate(formats):
        logger.info(f"Format {i+1}: ID={fmt.get('format_id')}, "
                   f"height={fmt.get('height')}, width={fmt.get('width')}, "
                   f"resolution={fmt.get('resolution')}, note={fmt.get('format_note')}, "
                   f"vcodec={fmt.get('vcodec')}, acodec={fmt.get('acodec')}, "
                   f"ext={fmt.get('ext')}, protocol={fmt.get('protocol')}")
    
    # Group formats by quality and find the best (most reliable) for each quality
    quality_groups = {}
    
    for fmt in formats:
        # Skip audio-only formats (no video codec), storyboards, and image formats
        vcodec = fmt.get('vcodec', 'none')
        ext = fmt.get('ext', '')
        format_note = fmt.get('format_note', '')
        
        if (vcodec == 'none' or vcodec is None or 
            ext in ['mhtml', 'jpg', 'png', 'webp'] or
            'storyboard' in format_note.lower()):
            continue
            
        # Get quality information - try multiple fields
        height = fmt.get('height', 0)
        resolution = fmt.get('resolution', '')
        format_id = fmt.get('format_id', '')
        filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
        protocol = fmt.get('protocol', 'https')
        
        # Determine quality label from multiple sources
        quality_label = None
        quality_height = 0
        
        # For YouTube Shorts and portrait videos, use the smaller dimension (width) as quality
        width = fmt.get('width', 0)
        if height and width and height > width:
            # Portrait video (height > width) - use width as quality indicator
            quality_label = f"{width}p"
            quality_height = width
        elif height and height > 0:
            # Regular landscape video - use height
            quality_label = f"{height}p"
            quality_height = height
        elif resolution and 'x' in resolution:
            # Parse resolution like "1280x720" or "360x640"
            try:
                res_width, res_height = resolution.split('x')
                res_width, res_height = int(res_width), int(res_height)
                if res_height > res_width:
                    # Portrait: use width as quality
                    quality_height = res_width
                    quality_label = f"{res_width}p"
                else:
                    # Landscape: use height as quality
                    quality_height = res_height
                    quality_label = f"{res_height}p"
            except (ValueError, AttributeError):
                pass
        elif format_note:
            # Extract quality from format_note like "720p", "1080p60", etc.
            import re
            quality_match = re.search(r'(\d+)p', format_note)
            if quality_match:
                quality_height = int(quality_match.group(1))
                quality_label = f"{quality_height}p"
        
        # For well-known YouTube format IDs, use hardcoded mappings
        if not quality_label:
            format_quality_map = {
                # Progressive MP4 formats
                '18': ('360p', 360),   # MP4 360p
                '22': ('720p', 720),   # MP4 720p  
                '37': ('1080p', 1080), # MP4 1080p
                '38': ('3072p', 3072), # MP4 4K
                # Adaptive MP4 formats (video only) - PREFER THESE
                '133': ('240p', 240),  # MP4 240p (video only)
                '134': ('360p', 360),  # MP4 360p (video only)
                '135': ('480p', 480),  # MP4 480p (video only)
                '136': ('720p', 720),  # MP4 720p (video only)
                '137': ('1080p', 1080), # MP4 1080p (video only)
                '138': ('2160p', 2160), # MP4 4K (video only)
                # High frame rate formats
                '298': ('720p60', 720),  # MP4 720p60
                '299': ('1080p60', 1080), # MP4 1080p60
                # WebM formats
                '242': ('240p', 240),  # WebM 240p
                '243': ('360p', 360),  # WebM 360p
                '244': ('480p', 480),  # WebM 480p
                '247': ('720p', 720),  # WebM 720p
                '248': ('1080p', 1080), # WebM 1080p
                # VP9 formats
                '278': ('144p', 144),  # WebM 144p VP9
                '394': ('144p', 144),  # MP4 144p AV1
                '395': ('240p', 240),  # MP4 240p AV1
                '396': ('360p', 360),  # MP4 360p AV1
                '397': ('480p', 480),  # MP4 480p AV1
                '398': ('720p', 720),  # MP4 720p AV1
                '399': ('1080p', 1080), # MP4 1080p AV1
                # 3D formats
                '82': ('360p', 360),   # MP4 360p 3D
                '83': ('480p', 480),   # MP4 480p 3D  
                '84': ('720p', 720),   # MP4 720p 3D
                '85': ('1080p', 1080), # MP4 1080p 3D
            }
            if format_id in format_quality_map:
                quality_label, quality_height = format_quality_map[format_id]
        
        # If we still don't have a quality, use format_id as fallback
        if not quality_label:
            quality_label = f"Format {format_id}"
            quality_height = 0
        
        # Calculate reliability score to prioritize formats
        reliability_score = 0
        
        # Prefer https protocol over m3u8/hls (m3u8 formats often fail)
        if protocol == 'https':
            reliability_score += 100
        elif protocol in ['m3u8', 'hls', 'm3u8_native']:
            reliability_score += 10  # Lower priority but still usable
        
        # Prefer mp4 over webm, prefer known formats
        if ext == 'mp4':
            reliability_score += 50
        elif ext == 'webm':
            reliability_score += 30
        
        # Prefer formats with filesize info
        if filesize and filesize > 0:
            reliability_score += 20
        
        # Prefer non-3D, non-HDR formats for general use
        if '3D' not in format_note and 'HDR' not in format_note:
            reliability_score += 10
        
        # Prefer non-"Untested" formats
        if 'Untested' not in format_note:
            reliability_score += 30
        
        # Group by quality and keep the most reliable format for each quality
        if quality_label not in quality_groups:
            quality_groups[quality_label] = []
        
        quality_groups[quality_label].append({
            'format_id': format_id,
            'quality': quality_label,
            'height': quality_height,
            'filesize': filesize,
            'ext': ext,
            'filesize_mb': (filesize / (1024 * 1024)) if filesize else 0,
            'vcodec': vcodec,
            'format_note': format_note,
            'protocol': protocol,
            'reliability_score': reliability_score,
        })
    
    # Select the best format for each quality
    video_formats = []
    for quality_label, formats_for_quality in quality_groups.items():
        # Sort by reliability score (highest first)
        formats_for_quality.sort(key=lambda x: x['reliability_score'], reverse=True)
        best_format = formats_for_quality[0]
        
        logger.info(f"Quality {quality_label}: Selected format {best_format['format_id']} "
                   f"(protocol: {best_format['protocol']}, score: {best_format['reliability_score']}) "
                   f"over {len(formats_for_quality)-1} alternatives")
        
        video_formats.append(best_format)
    
    # Sort by quality (height) descending, with fallback for unknown heights
    video_formats.sort(key=lambda x: (x['height'] if x['height'] > 0 else -1), reverse=True)
    
    # Limit to top 10 qualities to avoid inline keyboard limits
    final_formats = video_formats[:10]
    
    logger.info(f"Found {len(final_formats)} video formats: {[f['quality'] + ' (' + f['format_id'] + ')' for f in final_formats]}")
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
    
    logger.info(f"Starting {'audio' if is_audio_only else 'video'} download for {title} (format: {format_id})")
    
    await video_properties.download_message.edit_text(
        f"📥 <b>Downloading:</b> {title}\n"
        f"🎬 <b>Quality:</b> {'Audio Only' if is_audio_only else _get_quality_display_name(format_id, video_properties)}\n"
        f"⏳ Please wait...",
        parse_mode=ParseMode.HTML
    )
    
    temp_file = None
    try:
        temp_file = await _create_temp_file()
        downloaded_file_path = await _download_video_to_temp(url, temp_file, format_id, is_audio_only, video_properties)
        
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
        # Remove video from set to free memory (do this at the end)
        video_download_set.pop(video_properties.id, None)


async def _create_temp_file():
    """Create temporary file for download"""
    try:
        temp_dir = BASE_DIR / "data" / "temp"
        os.makedirs(temp_dir, exist_ok=True)
        return NamedTemporaryFile(dir=temp_dir, delete=False)
    except Exception as e:
        logger.error(f"Temp file creation error: {str(e)}")
        raise FileTempException("Temporary file creation failed.")


async def _download_video_to_temp(url: str, temp_file, format_id: str = None, is_audio_only: bool = False, video_properties: File = None) -> str:
    """Download video to temporary file using yt-dlp"""
    logger.info(f"Starting {'audio' if is_audio_only else 'video'} download - Format: {format_id}")
    
    try:
        # Base options with anti-bot detection measures
        base_opts = {
            'outtmpl': f'{temp_file.name}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            # Add headers to avoid bot detection
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip,deflate',
                'Connection': 'keep-alive',
            },
            # Extractor args for YouTube
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
            # Add delay to avoid rate limiting
            'sleep_interval': 1,
            'max_sleep_interval': 3,
        }
        
        # Prepare format-specific options with fallback
        if is_audio_only:
            ydl_opts = {
                **base_opts,
                'format': 'bestaudio/best',
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '192K',
            }
        else:
            if format_id:
                # Try specific format first, with intelligent fallbacks
                # Get the actual quality/height from the video properties
                selected_format_height = None
                
                if video_properties and 'formats' in video_properties.extra_data:
                    for fmt in video_properties.extra_data['formats']:
                        if fmt['format_id'] == format_id:
                            selected_format_height = fmt.get('height', 0)
                            break
                
                # Build format string with intelligent fallbacks
                format_string = format_id
                
                # Add fallbacks based on actual quality, not format ID number
                if selected_format_height and selected_format_height > 0:
                    # For specific quality, add fallbacks around that quality
                    format_string += f"/best[height<={selected_format_height}]"
                    if selected_format_height >= 720:
                        format_string += "/best[height<=720]"
                    format_string += "/best"
                else:
                    # Generic fallback if we can't determine quality
                    format_string += "/best"
                
                ydl_opts = {
                    **base_opts,
                    'format': format_string,
                }
                logger.info(f"Using format string for format_id {format_id} (height: {selected_format_height}): {format_string}")
            else:
                ydl_opts = {
                    **base_opts,
                    'format': 'best[height<=720]/best',  # Default to 720p with fallback
                }
        
        def download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                # If specific format fails, try with a more generic format
                logger.warning(f"Download failed with specific format, trying fallback: {str(e)}")
                if not is_audio_only and format_id:
                    fallback_opts = {
                        **base_opts,
                        'format': 'best[height<=720]/best',  # Fallback to best available
                    }
                    logger.info("Attempting download with fallback format: best[height<=720]/best")
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                        ydl.download([url])
                else:
                    raise
        
        # Run download in executor to avoid blocking
        await asyncio.get_event_loop().run_in_executor(None, download)
        
        # Close the temp file before searching for downloaded files
        temp_file.close()
        
        # Debug: Check what files were actually created
        temp_dir = os.path.dirname(temp_file.name)
        temp_basename = os.path.basename(temp_file.name)
        
        logger.info(f"Temp directory: {temp_dir}")
        logger.info(f"Looking for files starting with: {temp_basename}")
        
        all_files = os.listdir(temp_dir)
        logger.info(f"All files in temp directory: {all_files}")
        
        downloaded_files = [f for f in all_files if f.startswith(temp_basename)]
        logger.info(f"Matching downloaded files: {downloaded_files}")
        
        # Debug: Check file sizes
        for file in downloaded_files:
            file_path = os.path.join(temp_dir, file)
            file_size = os.path.getsize(file_path)
            logger.info(f"File {file}: {file_size} bytes")
        
        if not downloaded_files:
            logger.error("No file was downloaded by yt-dlp")
            raise DownloadException("No file was downloaded")
        
        # Select the largest file (actual video, not empty temp file)
        downloaded_file_path = None
        largest_size = 0
        
        for file in downloaded_files:
            file_path = os.path.join(temp_dir, file)
            file_size = os.path.getsize(file_path)
            
            # Select the file with the largest size (this will be the actual video)
            if file_size > largest_size:
                largest_size = file_size
                downloaded_file_path = file_path
        
        if not downloaded_file_path:
            logger.error("No valid downloaded file found")
            raise DownloadException("No valid downloaded file found")
            
        # Validate downloaded file
        if not os.path.exists(downloaded_file_path):
            raise DownloadException("Downloaded file not found")
            
        file_size = os.path.getsize(downloaded_file_path)
        logger.info(f"Final selected file: {downloaded_file_path} - Size: {file_size} bytes")
        
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


def _get_quality_display_name(format_id: str, video_properties: File) -> str:
    """Get the display name for a quality based on format ID"""
    if not format_id or not video_properties:
        return f"Video ({format_id})"
    
    # Look up the quality from the stored format data
    if 'formats' in video_properties.extra_data:
        for fmt in video_properties.extra_data['formats']:
            if fmt['format_id'] == format_id:
                quality = fmt.get('quality', f"Format {format_id}")
                return f"Video - {quality}"
    
    # Fallback if format not found
    return f"Video ({format_id})"