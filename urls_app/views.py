

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseGone, HttpResponseRedirect
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import ShortenedURL
from .serializers import (
    ShortenedURLSerializer,
    ShortenURLSerializer,
    URLAnalyticsSerializer,
)
from .throttles import URLCreateThrottle, RedirectThrottle


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_client_ip(request) -> str:
   
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


# ── ViewSet ───────────────────────────────────────────────────────────────────

class ShortenedURLViewSet(viewsets.ModelViewSet):
   

    permission_classes = [IsAuthenticated]
    # Default serializer; overridden per action in get_serializer_class()
    serializer_class = ShortenedURLSerializer

    # ── Queryset ──────────────────────────────────────────────────────────────

    def get_queryset(self):
       
        qs = ShortenedURL.objects.filter(owner=self.request.user)

        # Optional: filter by active status
        active_param = self.request.query_params.get("active")
        if active_param is not None:
            qs = qs.filter(is_active=active_param.lower() == "true")

        # Optional: simple keyword search
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(original_url__icontains=search) | qs.filter(
                title__icontains=search
            )

        return qs.order_by("-created_at")

    # ── Serializer routing ────────────────────────────────────────────────────

    def get_serializer_class(self):
        if self.action == "create":
            return ShortenURLSerializer
        return ShortenedURLSerializer

    # ── Throttle routing ──────────────────────────────────────────────────────

    def get_throttles(self):
        if self.action == "create":
            return [URLCreateThrottle()]
        return super().get_throttles()

    # ── Create (POST /api/shorten/) ───────────────────────────────────────────

    def create(self, request, *args, **kwargs):
        
        serializer = ShortenURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Inject the authenticated user as owner before saving
        url_obj = serializer.save(owner=request.user)

        # Return the full representation using the read serializer
        read_serializer = ShortenedURLSerializer(url_obj, context={"request": request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    # ── Update (PATCH/PUT /api/urls/<id>/) ────────────────────────────────────

    def update(self, request, *args, **kwargs):
        
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = ShortenedURLSerializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        url_obj = serializer.save()

        # Bust the cached redirect so the new destination is used immediately
        cache_key = f"redirect:{url_obj.short_code}"
        cache.delete(cache_key)

        return Response(ShortenedURLSerializer(url_obj).data)

    # ── Destroy (DELETE /api/urls/<id>/) ─────────────────────────────────────

    def destroy(self, request, *args, **kwargs):
       
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

        # Bust the redirect cache
        cache.delete(f"redirect:{instance.short_code}")

        return Response(
            {"message": f"URL '{instance.short_code}' has been deactivated."},
            status=status.HTTP_200_OK,
        )

    # ── Analytics (GET /api/urls/<id>/analytics/) ─────────────────────────────

    @action(detail=True, methods=["get"], url_path="analytics")
    def analytics(self, request, pk=None):
        
        url_obj = self.get_object()
        serializer = URLAnalyticsSerializer(url_obj)
        return Response(serializer.data)


# ── Public Redirect ───────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([RedirectThrottle])
def redirect_view(request, short_code: str):
   
    cache_key = f"redirect:{short_code}"

    # ── 1. Try Redis cache first ──────────────────────────────────────────────
    cached = cache.get(cache_key)
    if cached:
        # We stored a dict {"url": "...", "is_active": True, "expired": False}
        if not cached.get("is_active") or cached.get("expired"):
            return HttpResponseGone(
                content='{"error": "This link is no longer available."}',
                content_type="application/json",
            )

        # Record analytics asynchronously-ish (still synchronous here;
        # for high-traffic apps, push to a Celery task queue instead)
        _record_click_async(short_code, request)
        return HttpResponseRedirect(cached["url"])

    # ── 2. Cache miss → query DB ──────────────────────────────────────────────
    try:
        url_obj = ShortenedURL.objects.get(short_code=short_code)
    except ShortenedURL.DoesNotExist:
        return Response(
            {"error": f"Short URL '{short_code}' not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ── 3. Validate link state ────────────────────────────────────────────────
    if not url_obj.is_active:
        # Cache the inactive state briefly to avoid DB hammering
        cache.set(cache_key, {"url": "", "is_active": False, "expired": False}, timeout=60)
        return HttpResponseGone(
            content='{"error": "This link has been deactivated."}',
            content_type="application/json",
        )

    if url_obj.is_expired:
        cache.set(cache_key, {"url": "", "is_active": True, "expired": True}, timeout=60)
        return HttpResponseGone(
            content='{"error": "This link has expired."}',
            content_type="application/json",
        )

    # ── 4. Cache the valid redirect ───────────────────────────────────────────
    ttl = getattr(settings, "REDIRECT_CACHE_TTL", 86400)  # default 24 h
    cache.set(
        cache_key,
        {"url": url_obj.original_url, "is_active": True, "expired": False},
        timeout=ttl,
    )

    # ── 5. Record click analytics ─────────────────────────────────────────────
    url_obj.record_click(
        ip_address=_get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        referer=request.META.get("HTTP_REFERER", ""),
    )

    return HttpResponseRedirect(url_obj.original_url)


def _record_click_async(short_code: str, request) -> None:
    
    try:
        url_obj = ShortenedURL.objects.get(short_code=short_code)
        url_obj.record_click(
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            referer=request.META.get("HTTP_REFERER", ""),
        )
    except ShortenedURL.DoesNotExist:
        pass  # Edge case: object deleted between cache write and this call
