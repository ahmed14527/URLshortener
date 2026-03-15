

from django.contrib import admin
from django.utils.html import format_html

from .models import ClickEvent, ShortenedURL


class ClickEventInline(admin.TabularInline):
    model = ClickEvent
    extra = 0
    max_num = 10
    readonly_fields = ("clicked_at", "ip_address", "user_agent", "referer")
    can_delete = False
    ordering = ["-clicked_at"]


@admin.register(ShortenedURL)
class ShortenedURLAdmin(admin.ModelAdmin):
    list_display = (
        "short_code",
        "clickable_original",
        "owner",
        "click_count",
        "is_active",
        "is_custom",
        "expires_at",
        "created_at",
    )
    list_filter = ("is_active", "is_custom", "created_at")
    search_fields = ("short_code", "original_url", "owner__username", "title")
    readonly_fields = ("click_count", "last_accessed", "created_at", "updated_at")
    inlines = [ClickEventInline]
    ordering = ["-created_at"]

    def clickable_original(self, obj):
        display = obj.original_url[:60] + ("…" if len(obj.original_url) > 60 else "")
        return format_html('<a href="{}" target="_blank">{}</a>', obj.original_url, display)

    clickable_original.short_description = "Original URL"


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = ("shortened_url", "clicked_at", "ip_address", "referer")
    list_filter = ("clicked_at",)
    search_fields = ("shortened_url__short_code", "ip_address", "user_agent")
    readonly_fields = ("shortened_url", "clicked_at", "ip_address", "user_agent", "referer")
    ordering = ["-clicked_at"]
