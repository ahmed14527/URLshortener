

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class ShortenedURL(models.Model):
   

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shortened_urls",
        help_text="The user who owns this link.",
    )
    original_url = models.URLField(
        max_length=2048,
        help_text="The full destination URL.",
    )
    short_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique identifier used in the short URL path.",
    )
    is_custom = models.BooleanField(
        default=False,
        help_text="True if the user provided a custom alias.",
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional display name for the link.",
    )

    # ── Analytics ─────────────────────────────────────────────────────────────
    click_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of redirect hits. Updated atomically.",
    )
    last_accessed = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last successful redirect.",
    )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When set, redirects fail with 410 after this time.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive links return 410 Gone without being deleted.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Shortened URL"
        verbose_name_plural = "Shortened URLs"
        indexes = [
            models.Index(fields=["short_code"]),
            models.Index(fields=["owner", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.short_code} → {self.original_url[:60]}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        """True if an expiry was set and it has passed."""
        return self.expires_at is not None and timezone.now() > self.expires_at

    def record_click(self, ip_address: str = "", user_agent: str = "", referer: str = "") -> None:
       
        from django.db.models import F

        ShortenedURL.objects.filter(pk=self.pk).update(
            click_count=F("click_count") + 1,
            last_accessed=timezone.now(),
        )

        # Create the detailed analytics record
        ClickEvent.objects.create(
            shortened_url=self,
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else "",
            referer=referer[:2048] if referer else "",
        )


class ClickEvent(models.Model):
   

    shortened_url = models.ForeignKey(
        ShortenedURL,
        on_delete=models.CASCADE,
        related_name="click_events",
    )
    clicked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Visitor IP address.",
    )
    user_agent = models.CharField(max_length=512, blank=True, default="")
    referer = models.CharField(
        max_length=2048,
        blank=True,
        default="",
        verbose_name="HTTP Referer",
    )

    class Meta:
        ordering = ["-clicked_at"]
        verbose_name = "Click Event"
        verbose_name_plural = "Click Events"
        indexes = [
            models.Index(fields=["shortened_url", "-clicked_at"]),
        ]

    def __str__(self):
        return f"Click on {self.shortened_url.short_code} at {self.clicked_at}"
