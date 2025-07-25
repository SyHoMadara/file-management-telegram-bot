# 🚀 Telegram File Manager Bot

![Bot Demo](telegram_preview_bot.gif)

> 🤖 **Live Bot**: Try it now at [@file_download_management_bot](https://t.me/file_download_management_bot)

A powerful and feature-rich Telegram bot built with Django and MinIO for efficient file management and storage. This bot allows users to upload, store, and download files up to 2GB with automatic storage cleanup using Celery Beat.

## ✨ Features

- 📁 **Large File Support**: Handle files up to 2GB
- 🎬 **Video Download**: Download videos from YouTube and other platforms with yt-dlp
- 🎛️ **Quality Selection**: Choose from multiple video qualities via inline buttons
- 🍪 **Anti-Bot Protection**: Cookie support to bypass YouTube restrictions
- 🔐 **User Management**: Premium user system with download quotas
- 💎 **Premium Requests**: Users can request premium access via `/premium` command
- 🔔 **Admin Notifications**: Automatic notifications for premium requests and promotions
- 📊 **Download Quotas**: Daily download limits with premium/regular user tiers
- ⚠️ **Size Validation**: Pre-download file size validation with quota warnings
- 📏 **Smart Limits**: Different file size limits for premium vs regular users
- ⏰ **Automatic Cleanup**: Celery Beat tasks for storage management
- 🌐 **Multi-language Support**: English and Persian (Farsi)
- 📊 **Admin Panel**: Django admin interface for management
- 🗄️ **MinIO Storage**: Scalable object storage backend
- 📱 **Telegram Integration**: Built with Pyrogram for robust bot functionality
- 🔄 **Real-time Monitoring**: Flower for Celery task monitoring

## 🛠️ Tech Stack

- **Backend**: Django 5.2.4
- **Bot Framework**: Pyrogram 2.0.106
- **Video Downloader**: yt-dlp 2024.12.13
- **Storage**: MinIO Object Storage
- **Task Queue**: Celery with Redis
- **Database**: SQLite (configurable)
- **Containerization**: Docker & Docker Compose

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │◄──►│  Django Backend │◄──►│  MinIO Storage  │
│   (Pyrogram)    │    │   (REST API)    │    │  (File Storage) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         └──────────────►│ Celery Worker   │◄─────────────┘
                        │ (Background     │
                        │  Tasks)         │
                        └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Redis (Broker)  │
                        │ & Results       │
                        └─────────────────┘
```

## 📋 Prerequisites

- Docker and Docker Compose
- Python 3.13+ (if running locally)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) - Fast Python package manager
- Telegram Bot Token (from @BotFather)
- Telegram API credentials (api_id, api_hash)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd telbot_downloader
```

### 2. Environment Setup

Create a `.env` file in the root directory:

```env
# Django Settings
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Telegram Bot Configuration
TELEGRAM_BOT_API_TOKEN=your-bot-token-here
TELEGRAM_API_ID=your-api-id
TELEGRAM_API_HASH=your-api-hash

# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_EXTERNAL_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_USE_HTTPS=False

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Download Limits (in MB)
MAX_PREMIUM_DOWNLOAD_SIZE=500
MAX_REGULAR_DOWNLOAD_SIZE=100

# File size limits for different user types
PREMIUM_DAILY_QUOTA=2000  # 2GB daily for premium users
REGULAR_DAILY_QUOTA=500   # 500MB daily for regular users

# Internationalization
DJANGO_LANGUAGE_CODE=en-us
DJANGO_TIME_ZONE=Asia/Tehran
```

### 3. Start MinIO Storage

```bash
docker-compose -f docker-compose-minio.yml up -d
```

### 4. Start the Bot Backend

```bash
docker-compose -f docker-compose-bot.yml up -d --build
```

## 🔧 Access Points

### 📊 Django Admin Panel
- **URL**: `http://localhost:8383/admin/`
- **Description**: Manage users, files, and bot settings
- **Default Credentials**: Create superuser with `python manage.py createsuperuser`

### 🗄️ MinIO Console
- **URL**: `http://localhost:9001`
- **Username**: `minioadmin` (from MINIO_ACCESS_KEY)
- **Password**: `minioadmin123` (from MINIO_SECRET_KEY)
- **Description**: Manage object storage, buckets, and files

### 🌸 Flower (Celery Monitoring)
- **URL**: `http://localhost:5555`
- **Description**: Monitor Celery tasks, workers, and queues
- **Features**: Real-time task monitoring, worker statistics

### 🔌 MinIO API Endpoint
- **URL**: `http://localhost:9000`
- **Description**: MinIO S3-compatible API endpoint
- **Usage**: For direct S3 API access and integrations

## 📝 Usage

### Bot Commands

- `/start` - Initialize the bot and create user account
- `/help` - Display help information and available features
- `/premium` - Request premium access for unlimited downloads
- `/lang` or `/language` - Change bot language (English/Persian)

### File Operations

1. **Upload Files**: Send any document to the bot (up to 2GB)
   - Files are validated against user quotas
   - Premium users have higher limits
   - File size warnings for quota/limit exceeded files
2. **Download Videos**: Send a YouTube URL or other supported video link
   - Select from multiple quality options (144p to 4K)
   - Choose between video or audio-only downloads
   - Bot automatically finds the best available formats
   - Pre-download size validation with quota warnings
   - Quality buttons show warnings (⚠️) if file exceeds limits
3. **Download**: Click the download button to get a secure download link
4. **Premium Access**: Use `/premium` command to request unlimited downloads
   - Admins receive automatic notifications for new requests
   - Users are notified when promoted to premium status
5. **Quota Management**: 
   - Regular users: 100MB per file, 500MB daily quota
   - Premium users: 500MB per file, 2GB daily quota
   - Quotas reset daily at midnight

### Video Download Features

- **Supported Platforms**: YouTube, Twitter, TikTok, and 1000+ sites via yt-dlp
- **Quality Selection**: Interactive buttons for different video qualities
- **Smart Fallbacks**: Automatically selects best available format if requested quality unavailable
- **Anti-Bot Protection**: Cookie support to bypass platform restrictions
- **Format Options**: MP4, WebM, Audio-only (MP3)
- **Size Validation**: Pre-download validation with quota checking
- **Warning System**: Quality buttons show ⚠️ for files exceeding limits
- **Smart Error Messages**: Short, informative popup messages for quota issues
- **Audio Downloads**: Separate validation for audio-only downloads

### Callback Handler Features

The bot includes sophisticated inline keyboard handling:

- **Quality Selection**: Interactive buttons for video quality selection
- **Size Warnings**: Buttons show ⚠️ for files exceeding quotas/limits
- **Error Handling**: Smart error messages for quota/size issues
- **Audio Downloads**: Separate validation and handling for audio files
- **Session Management**: Temporary video sessions for quality selection
- **Callback Validation**: Proper validation of all callback data patterns

### Error Messages

All popup messages are optimized for Telegram's callback answer limits:
- Short, concise error messages
- Clear size/quota information
- Actionable suggestions (/premium upgrade)
- No overly long text that gets truncated

## 🔄 Automatic Cleanup

The bot includes Celery Beat scheduled tasks for:

- **File Cleanup**: Automatically removes old files based on `MINIO_URL_EXPIRY_HOURS`
- **Storage Management**: Maintains optimal storage usage
- **Database Cleanup**: Removes orphaned records

Configure cleanup intervals in the Django admin panel under **Periodic Tasks**.

## 🍪 YouTube Cookies Configuration

To bypass YouTube's bot detection and access more video formats, you can add browser cookies:

### Quick Setup

1. **Install Browser Extension**
   - Chrome/Edge: "Get cookies.txt LOCALLY"
   - Firefox: "cookies.txt"

2. **Export Cookies**
   - Visit youtube.com while logged in
   - Use the extension to export cookies
   - Copy the exported data

3. **Add to Bot**
   - Open `data/cookies/youtube_cookies.txt`
   - Replace content with exported cookies
   - Restart the bot

### Benefits
- Access to more video quality options
- Reduced rate limiting
- Better success rate for restricted videos
- Support for age-restricted content

See `data/cookies/README.md` for detailed instructions.

## 💎 Premium System

The bot includes a comprehensive premium user management system:

### For Users
- **Request Premium**: Use `/premium` command to request premium access
- **Anti-Spam Protection**: System prevents duplicate requests
- **Status Check**: Command shows if you're already premium
- **Automatic Notifications**: Get notified when promoted to premium

### For Administrators
- **Request Notifications**: Receive instant notifications when users request premium
- **Admin Panel**: Manage premium users through Django admin interface
- **User Information**: View detailed user info including:
  - Full name and username
  - Telegram user ID
  - Request date and time
  - Premium status and request history
- **Easy Promotion**: Simply set `is_premium=True` in admin panel
- **Automatic Notifications**: Users are automatically notified when promoted

### Premium Features
- **Higher File Limits**: Up to 500MB per file vs 100MB for regular users
- **Larger Daily Quota**: 2GB daily downloads vs 500MB for regular users  
- **Priority Processing**: Faster file processing
- **Enhanced Speeds**: Improved download performance
- **All File Formats**: Access to all supported file types
- **Auto Quota Reset**: Daily quota automatically resets at midnight

### Admin Workflow
1. User sends `/premium` command
2. Admin receives notification with user details
3. Admin reviews request in Django admin panel
4. Admin promotes user by setting `is_premium=True`
5. User automatically receives promotion notification

## 🛠️ Development

### Local Development Setup

1. **Install uv (if not already installed)**:
   ```bash
   # On macOS and Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # On Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # Or using pip
   pip install uv
   ```

2. **Install Dependencies**:
   ```bash
   uv sync
   ```

3. **Database Migration**:
   ```bash
   uv run python manage.py migrate
   ```

4. **Create Superuser**:
   ```bash
   uv run python manage.py createsuperuser
   ```

5. **Run Development Server**:
   ```bash
   uv run python manage.py runserver
   ```

6. **Start Celery Worker**:
   ```bash
   uv run celery -A config worker -l info
   ```

7. **Start Celery Beat**:
   ```bash
   uv run celery -A config beat -l info
   ```

### Project Structure

```
telbot_downloader/
├── apps/
│   ├── account/          # User management
│   ├── file_manager/     # File storage models
│   └── telegram_bot/     # Bot logic and handlers
├── config/               # Django settings
├── data/                 # SQLite DB, logs, sessions
├── docker-compose-bot.yml    # Bot services
├── docker-compose-minio.yml  # MinIO storage
└── pyproject.toml        # Python dependencies
```

## 🔒 Security Features

- **User Quotas**: Prevent abuse with download limits (500MB/2GB daily)
- **File Size Limits**: 100MB (regular) / 500MB (premium) per file
- **Premium System**: Request-based premium access with admin approval
- **Anti-Spam Protection**: Prevents duplicate premium requests
- **File Validation**: Size validation before and after download
- **Smart Warnings**: Interactive buttons warn about quota/limit issues
- **Secure URLs**: Time-limited download links
- **Admin Controls**: Full administrative oversight with notification system

## 📈 Monitoring & Logs

- **Application Logs**: Available in `data/logs/app.log`
- **Celery Monitoring**: Access Flower dashboard at `http://localhost:5555`
- **MinIO Metrics**: Built-in MinIO console monitoring
- **Django Debug**: Enable with `DJANGO_DEBUG=True`

## 🌍 Internationalization

The bot supports multiple languages:
- **English** (default)
- **Persian/Farsi**

Language files are located in `apps/telegram_bot/locale/`.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the logs in `data/logs/app.log`
2. Monitor Celery tasks in Flower
3. Verify MinIO connectivity
4. Review Django admin for user/file management

## 🔮 Future Enhancements

- [ ] File encryption at rest
- [ ] Advanced user analytics
- [ ] Multiple storage backends
- [ ] API rate limiting
- [ ] File compression options
- [ ] Backup and restore functionality

---

**Built with ❤️ using Django, Pyrogram, and MinIO**