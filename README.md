# URL Shortener API

A production-ready URL shortening service built with **Django 4.2**, **Django REST Framework**, **db.sqlite3**, and **Redis**.

---

## Features

| Feature            | Detail                                                  |
| ------------------ | ------------------------------------------------------- |
| JWT Authentication | Register, login, logout, token refresh via `simplejwt`  |
| URL Shortening     | Auto-generated 6-char codes or custom aliases           |
| Redis Caching      | 24-hour cache on redirect lookups for near-zero latency |
| Click Analytics    | Per-click events (IP, UA, Referer) + aggregate counters |
| Link Expiry        | Optional `expires_at` datetime per link                 |
| Soft Delete        | Deactivating a link preserves analytics                 |
| Rate Limiting      | 10 URL creations/min per user; 30 anon redirects/min    |
| Pagination         | All list endpoints paginated (20 per page)              |
| Search & Filter    | `?search=` and `?active=` query params on list          |

---

## Project Structure

```
urlshortener/
├── config/
│   ├── settings.py          # Django + DRF + JWT + Redis configuration
│   ├── urls.py              # Root URL configuration
│   └── wsgi.py
│
├── authentication/
│   ├── serializers.py       # Register, Login, Profile serializers
│   ├── views.py             # register, login, logout, me views
│   └── urls.py
│
├── urls_app/
│   ├── models.py            # ShortenedURL, ClickEvent models
│   ├── serializers.py       # URL serializers + analytics
│   ├── services.py          # Short code generation logic
│   ├── views.py             # ShortenedURLViewSet + redirect view
│   ├── throttles.py         # Rate limiting classes
│   ├── admin.py
│   └── urls.py
│
├── docs/
│   └── postman_collection.json
│
├── db.sqlite3               # SQLite database file
├── requirements.txt
└── .env.example
```

The API is now live at `http://localhost:8000`.

---

## API Reference

### Authentication

All protected endpoints require:

```
Authorization: Bearer <access_token>
```

---

#### `POST /api/auth/register`

Create a new account. Returns JWT tokens immediately.

**Request**

```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "StrongPass123!",
  "confirm_password": "StrongPass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response `201`**

```json
{
  "message": "Account created successfully.",
  "user": { "id": 1, "username": "johndoe", "email": "john@example.com" },
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

---

#### `POST /api/auth/login`

**Request**

```json
{ "username": "johndoe", "password": "StrongPass123!" }
```

**Response `200`**

```json
{
  "message": "Login successful.",
  "user": { "id": 1, "username": "johndoe", "email": "john@example.com" },
  "tokens": { "access": "eyJ...", "refresh": "eyJ..." }
}
```

---

#### `POST /api/auth/logout` 🔒

Blacklists the refresh token.

```json
{ "refresh": "<refresh_token>" }
```

---

#### `POST /api/auth/refresh`

Exchange a refresh token for a new access token.

```json
{ "refresh": "<refresh_token>" }
```

---

#### `GET /api/auth/me` 🔒

Returns the authenticated user's profile.

---

### URL Management

---

#### `POST /api/shorten/` 🔒 ⚡ Rate limited: 10/min

Shorten a URL.

**Request**

```json
{
  "original_url": "https://very-long-website.com/path?query=value",
  "custom_alias": "my-link",
  "title": "My Link",
  "expires_at": "2025-12-31T23:59:59Z"
}
```

> `custom_alias`, `title`, and `expires_at` are all optional.

**Response `201`**

```json
{
  "id": 1,
  "owner": "johndoe",
  "original_url": "https://very-long-website.com/path?query=value",
  "short_code": "my-link",
  "short_url": "http://localhost:8000/r/my-link/",
  "is_custom": true,
  "title": "My Link",
  "click_count": 0,
  "last_accessed": null,
  "expires_at": "2025-12-31T23:59:59Z",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error `400` — alias taken**

```json
{
  "custom_alias": [
    "The alias 'my-link' is already taken. Please choose another."
  ]
}
```

---

#### `GET /api/urls/` 🔒

List all your shortened URLs. Supports pagination and filtering.

**Query params**

| Param    | Description            | Example          |
| -------- | ---------------------- | ---------------- |
| `page`   | Page number            | `?page=2`        |
| `active` | Filter by active state | `?active=true`   |
| `search` | Search URL and title   | `?search=github` |

**Response `200`**

```json
{
  "count": 42,
  "next": "http://localhost:8000/api/urls/?page=3",
  "previous": "http://localhost:8000/api/urls/?page=1",
  "results": [ { ...url object... }, ... ]
}
```

---

#### `GET /api/urls/<id>/` 🔒

Retrieve a single URL by its database ID.

---

#### `PATCH /api/urls/<id>/` 🔒

Update the destination URL, title, expiry, or active status.
Automatically busts the Redis cache for this short code.

**Request** (all fields optional)

```json
{
  "original_url": "https://new-destination.example.com",
  "title": "New Title",
  "expires_at": "2026-06-30T00:00:00Z",
  "is_active": true
}
```

---

#### `DELETE /api/urls/<id>/` 🔒

Soft-deletes the URL (sets `is_active = false`). Analytics are preserved.

**Response `200`**

```json
{ "message": "URL 'my-link' has been deactivated." }
```

---

#### `GET /api/urls/<id>/analytics/` 🔒

Detailed analytics for one URL.

**Response `200`**

```json
{
  "url_id": 1,
  "short_code": "my-link",
  "short_url": "http://localhost:8000/r/my-link/",
  "original_url": "https://very-long-website.com/...",
  "title": "My Link",
  "click_count": 127,
  "last_accessed": "2024-01-16T08:22:00Z",
  "created_at": "2024-01-15T10:30:00Z",
  "recent_clicks": [
    {
      "id": 127,
      "clicked_at": "2024-01-16T08:22:00Z",
      "ip_address": "203.0.113.42",
      "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
      "referer": "https://twitter.com"
    }
  ]
}
```

---

### Redirect (Public)

#### `GET /r/<short_code>/`

No authentication required. Returns `302 Location: <original_url>`.

| Status     | Meaning                     |
| ---------- | --------------------------- |
| `302`      | Successful redirect         |
| `404`      | Short code not found        |
| `410 Gone` | Link deactivated or expired |

---

## Architecture Notes

### Caching Strategy

```
Redirect request ──► Redis hit? ──Yes──► 302 Redirect + record click
                        │
                        No
                        ▼
                     Query SQLite
                        │
                   Active & valid?
                     /        \
                   No          Yes
                   ▼            ▼
               410 Gone   Cache in Redis (24h)
                               │
                               ▼
                          302 Redirect
                        + record click
```

### Short Code Generation

Uses Python's `secrets` module (CSPRNG) to generate a 6-character alphanumeric code from a 62-char alphabet (a-z, A-Z, 0-9). With a 6-char code that gives 62⁶ = **56 billion** possible combinations. A collision causes a retry (up to 10 attempts, increasing code length after 5).

### Click Counter Concurrency

`ShortenedURL.record_click()` uses Django's `F()` expression for the counter increment, issuing a single `UPDATE … SET click_count = click_count + 1` SQL statement. This avoids the read-modify-write race condition common in high-traffic scenarios.

### Rate Limiting

| Endpoint                | Limit            |
| ----------------------- | ---------------- |
| `POST /api/shorten/`    | 10/min per user  |
| Authenticated endpoints | 100/min per user |
| Anonymous redirect      | 30/min per IP    |
