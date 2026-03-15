

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import ClickEvent, ShortenedURL
from .services import generate_short_code, validate_custom_alias


# ── Click Event ───────────────────────────────────────────────────────────────

class ClickEventSerializer(serializers.ModelSerializer):
   
    class Meta:
        model = ClickEvent
        fields = ("id", "clicked_at", "ip_address", "user_agent", "referer")
        read_only_fields = fields


# ── Shortened URL (full) ──────────────────────────────────────────────────────

class ShortenedURLSerializer(serializers.ModelSerializer):
    

    # Computed read-only field: the full short URL
    short_url = serializers.SerializerMethodField()

    # Make owner read-only; it's always set from request.user in the view
    owner = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ShortenedURL
        fields = (
            "id",
            "owner",
            "original_url",
            "short_code",
            "short_url",
            "is_custom",
            "title",
            "click_count",
            "last_accessed",
            "expires_at",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "owner",
            "short_code",
            "short_url",
            "is_custom",
            "click_count",
            "last_accessed",
            "created_at",
            "updated_at",
        )

    def get_short_url(self, obj: ShortenedURL) -> str:
        """Construct the full redirect URL, e.g. http://short.ly/r/aB3xY9"""
        base = getattr(settings, "BASE_URL", "http://localhost:8000").rstrip("/")
        return f"{base}/r/{obj.short_code}/"

    def validate_expires_at(self, value):
        """Expiry must be in the future."""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future.")
        return value


# ── Shorten (write) ───────────────────────────────────────────────────────────

class ShortenURLSerializer(serializers.Serializer):
   

    original_url = serializers.URLField(
        max_length=2048,
        help_text="The full URL to shorten.",
    )
    custom_alias = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional custom alias (3–30 alphanumeric chars, hyphens, underscores).",
    )
    title = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
    )
    expires_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Optional ISO-8601 expiry datetime.",
    )

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future.")
        return value

    def validate(self, attrs):
        """
        Resolve the short_code:
          - If custom_alias is provided → validate & use it
          - Otherwise             → auto-generate
        """
        alias = attrs.get("custom_alias", "").strip()

        if alias:
            try:
                attrs["short_code"] = validate_custom_alias(alias)
                attrs["is_custom"] = True
            except ValueError as exc:
                raise serializers.ValidationError({"custom_alias": str(exc)})
        else:
            attrs["short_code"] = generate_short_code()
            attrs["is_custom"] = False

        return attrs

    def create(self, validated_data):
        """Create and return a ShortenedURL. Owner is injected by the view."""
        # Remove write-only helper field that's not on the model
        validated_data.pop("custom_alias", None)
        return ShortenedURL.objects.create(**validated_data)


# ── Analytics summary ─────────────────────────────────────────────────────────

class URLAnalyticsSerializer(serializers.Serializer):
    """
    Aggregated analytics data returned from GET /api/urls/<id>/analytics/

    Includes summary stats plus the most recent click events.
    """

    url_id = serializers.IntegerField(source="id")
    short_code = serializers.CharField()
    short_url = serializers.SerializerMethodField()
    original_url = serializers.CharField()
    title = serializers.CharField()

    # Summary stats
    click_count = serializers.IntegerField()
    last_accessed = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()

    # Recent clicks (latest 50)
    recent_clicks = serializers.SerializerMethodField()

    def get_short_url(self, obj: ShortenedURL) -> str:
        base = getattr(settings, "BASE_URL", "http://localhost:8000").rstrip("/")
        return f"{base}/r/{obj.short_code}/"

    def get_recent_clicks(self, obj: ShortenedURL):
        """Return the 50 most recent ClickEvent records."""
        events = obj.click_events.order_by("-clicked_at")[:50]
        return ClickEventSerializer(events, many=True).data
