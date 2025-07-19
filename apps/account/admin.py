from django.contrib import messages
from django.contrib.admin import register
from django.contrib.auth.admin import UserAdmin as ModelAdmin
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import User


@register(User)
class UserAdmin(ModelAdmin):
    list_display = (
        "username",
        "telegram_id",
        "first_name",
        "last_name",
        "date_create",
        "date_update",
        "is_verified",
    )
    search_fields = ("username", "phone_number", "telegram_id" )
    ordering = ("-date_create",)
    list_filter = ("is_staff", "is_active")
    readonly_fields = ("date_create", "date_update", "reset_download_size_button")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "telegram_id")}),
        (
            ("Limits"),
            {
                "fields": (
                    "remaining_download_size",
                    "maximum_download_size_per_day",
                    "is_premium",
                    "reset_download_size_button",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_active",
                    "is_verified",
                )
            },
        ),
        ("Important dates", {"fields": ("date_create", "date_update")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "is_verified",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )

    def reset_download_size_button(self, obj):
        """Display a reset button for individual user"""
        if obj.pk:  # Only show for existing users
            url = reverse("admin:reset_user_download", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}">🔄 Reset Download Limit</a>', url
            )
        return "Save user first"

    def get_urls(self):
        """Add custom URL for reset action"""
        urls = super().get_urls()
        custom_urls = [
            path(
                "reset-download/<int:user_id>/",
                self.admin_site.admin_view(self.reset_individual_download),
                name="reset_user_download",
            ),
        ]
        return custom_urls + urls

    def reset_individual_download(self, request, user_id):
        """Reset download limit for individual user"""
        try:
            user = User.objects.get(pk=user_id)
            user.remaining_download_size = user.maximum_download_size_per_day
            user.save(update_fields=["remaining_download_size"])

            messages.success(
                request,
                f"Successfully reset download limit for user '{user.username}' "
                f"to {user.maximum_download_size_per_day} MB",
            )
        except User.DoesNotExist:
            messages.error(request, "User not found")

        return redirect("admin:account_user_change", user_id)

    def reset_download_max_size(self, request, queryset):
        updated_count = 0
        for user in queryset:
            user.remaining_download_size = user.maximum_downloads_per_day
            user.save(update_fields=["remaining_download_size"])
            updated_count += 1

        self.message_user(
            request,
            f"Successfully reset remaining download size for {updated_count} user(s) to their maximum daily limit.",
        )

    reset_download_max_size.short_description = (
        "Reset remaining download size to daily maximum"
    )

    # Add the action to the admin
    actions = ["reset_download_max_size"]
