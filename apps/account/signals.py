import logging
import threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from .models import User

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def notify_premium_promotion(sender, instance, created, **kwargs):
    """
    Signal handler to notify user when they're promoted to premium
    """
    if not created:  # Only for updates, not new user creation
        # Check if the user was just promoted to premium
        if instance.is_premium and instance.premium_requested:
            # Reset the premium_requested flag since it's now granted
            User.objects.filter(pk=instance.pk).update(premium_requested=False)
            
            # Send notification to user in a separate thread
            if instance.username:
                thread = threading.Thread(
                    target=send_premium_promotion_notification_sync,
                    args=(instance.username,)
                )
                thread.daemon = True
                thread.start()

def send_premium_promotion_notification_sync(username):
    """
    Send notification to user that they've been promoted to premium (sync version)
    """
    try:
        import asyncio
        asyncio.run(send_premium_promotion_notification(username))
    except Exception as e:
        logger.error(f"Failed to run premium promotion notification: {e}")

async def send_premium_promotion_notification(username):
    """
    Send notification to user that they've been promoted to premium
    """
    try:
        from pyrogram import Client
        import os
        from config.settings import BASE_DIR
        
        BOT_TOKEN = os.environ.get("TELEGRAM_BOT_API_TOKEN", "")
        API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
        API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
        
        if not BOT_TOKEN or not API_ID or not API_HASH:
            logger.error("Bot credentials not configured for premium notification")
            return
            
        app = Client(
            "premium_notification_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workdir=str(BASE_DIR / "data" / "pyrogram"),
        )
        
        promotion_message = (
            "🎉 **Congratulations!**\n\n"
            "✅ You have been promoted to **Premium**!\n\n"
            "🌟 **Premium Features Activated:**\n"
            "• Unlimited daily downloads\n"
            "• Priority processing\n"
            "• Access to all file formats\n"
            "• Enhanced download speeds\n\n"
            "💎 Thank you for being a valued user!\n"
            "Enjoy your premium experience! 🚀"
        )
        
        async with app:
            await app.send_message(int(username), promotion_message)
            logger.info(f"Premium promotion notification sent to user {username}")
            
    except Exception as e:
        logger.error(f"Failed to send premium promotion notification to user {username}: {e}")
