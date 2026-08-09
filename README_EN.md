# Ceryle — Document Rendering Service
https://github.com/CheesePanzer/Ceryle

An autonomous document rendering service built on FastAPI + docxtpl. Populates Word templates (.docx) with JSON data to generate formatted documents automatically.

---

## Features

- **Template Rendering**: Fills Word templates with JSON data using Jinja2 syntax to produce .docx files
- **Image Embedding**: Supports Base64-encoded images and remote URL images with automatic fetching and embedding; image dimensions are controlled via Jinja2 filters within the template: {{ image_variable | img(width=x, height=y) }}
- **Caching**: SHA-256 hash-based caching keyed on request data + template fingerprint — identical inputs hit the cache directly, avoiding redundant rendering
- **Sync & Async Modes**: Small files can be returned synchronously; large files submit an async task and poll for pickup
- **Template Management**: Upload, download, list, and delete templates; swappable storage backend (local filesystem / S3)
- **Admin Dashboard**: Web-based interface for system status monitoring, template management, cache clearing, and task cleanup

---

## API Reference

All APIs are prefixed with `/api/v1`. All endpoints except System require API Key authentication.

### Authentication

Include the `X-Api-Key` header in requests:

```
X-Api-Key: <your-api-key>
```

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check; returns service status, version, and timestamp |
| `GET` | `/` | Redirects to `/health` |

**`GET /health` response example:**

```json
{
  "status": "Healthy",
  "timestamp": 1718200000.123,
  "datetime": "2026-06-13 12:00:00",
  "service": "Ceryle",
  "version": "1.0.0"
}
```

---

### Render

#### Synchronous Rendering

```
POST /api/v1/generate/{template_name}
```

Renders a template and returns the .docx file stream. Suitable for small files.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `template_name` | string | Template file name (e.g., `contract.docx`) |

**Request Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `expectName` | string | No | Desired output file name (with or without extension) |
| `data` | object | Yes | Render data as a JSON object; keys correspond to template variable names |
| `images` | array | No | List of image data objects |

**Image Data (`ImageData`) structure:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `varName` | string | Yes | Image variable name used in the template |
| `imageSource` | string | Yes | Image source: Base64 data URI or HTTP/HTTPS URL |
| `realName` | string | No | Image title / description |

**Response Headers:**

| Header | Description |
|--------|-------------|
| `Content-Disposition` | File download as `attachment; filename=xxx.docx` |
| `X-File-Hash` | SHA-256 hash of the rendered output |
| `X-Is-Cache` | `Y` for cache hit, `N` for fresh render |

**Request Example:**

```json
{
  "expectName": "sales_order_2026",
  "data": {
    "customer_name": "John Doe",
    "order_date": "2026-06-13",
    "items": [
      { "name": "Product A", "qty": 10, "price": 99.00 },
      { "name": "Product B", "qty": 5, "price": 199.00 }
    ],
    "total": 1985.00
  },
  "images": [
    {
      "varName": "company_logo",
      "imageSource": "https://example.com/logo.png",
      "realName": "Company Logo"
    }
  ]
}
```

---

#### Submit Async Task

```
POST /api/v1/task/{template_name}
```

Submits a rendering task and returns a task ID immediately. Suitable for large files or batch rendering.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `template_name` | string | Template file name |

**Request Body:** Same as above (`DataRequest`)

**Response:** Returns a task ID as a UUID string, e.g. `"550e8400-e29b-41d4-a716-446655440000"`

> Returns `429 Too Many Requests` when the queue is full.

---

#### Download Async Task Result

```
GET /api/v1/task/file/{task_id}
```

Downloads the rendered .docx file by task ID.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | UUID | Task ID |

**Response:**
- Task complete: returns the .docx file stream
- `425 Too Early`: task not yet complete (pending / running)
- `404 Not Found`: task does not exist
- `500 Internal Server Error`: task failed; response body contains error details

---

### Management (Template Management)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/templates` | List all registered templates |
| `POST` | `/api/v1/templates/upload` | Upload a new template |
| `POST` | `/api/v1/templates/{template_name}/delete` | Delete a specified template |

#### List Templates

```
GET /api/v1/templates
```

Returns a list of filenames for all registered templates.

#### Upload Template

```
POST /api/v1/templates/upload
```

**Form Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | Yes | Template file (.docx only) |
| `overwrite` | bool | No | Whether to overwrite an existing template with the same name; default `false` |

> Uploading non-.docx files will result in an error.

#### Delete Template

```
POST /api/v1/templates/{template_name}/delete
```

Deletes the specified template file.

---

## Admin Dashboard

The admin dashboard is available at `/admin` and provides a web-based interface for visual management. Session-based login authentication is required.

### Pages

| Path | Function |
|------|----------|
| `/admin/login` | Admin login |
| `/admin/` | Dashboard — view service configuration, queue status, and task statistics |
| `/admin/templates` | Template management — upload, download, and delete templates |
| `/admin/tasks` | Task list — view the status of all tasks |
| `/admin/status` | Queue status API — returns queue length, worker count, and task statistics |
| `/admin/cache/clear` | One-click cache flush |
| `/admin/jobs/cleanup-stuck-queue` | Fail tasks that have timed out in the queue |
| `/admin/jobs/cleanup-stuck-processing` | Fail tasks that have timed out during processing |
| `/admin/jobs/cleanup-expired-results` | Clean up expired completed task results |

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `APP_NAME` | `Ceryle` | Service name |
| `APP_VERSION` | `1.0.0` | Service version |
| `APP_ENV` | `development` | Runtime environment (Swagger docs enabled in `development`) |
| `API_KEY` | — | API authentication key |
| `WORKER_COUNT` | `1` | Number of async render worker coroutines |
| `TASK_QUEUE_SIZE` | `50` | Maximum task queue length; returns 429 when exceeded |
| `STORAGE_BACKEND` | `local` | Template storage backend: `local` or `s3` |
| `TEMPLATE_DIR` | `templates` | Local template storage directory |
| `CACHE_DIR` | `cache` | Cache directory |
| `RESULT_DIR` | `result` | Async task result directory |
| `IMAGE_FETCH_TIMEOUT` | `2` | Remote image fetch timeout (seconds) |
| `ALLOWED_IMAGE_DOMAINS` | `[]` (unrestricted) | Remote image domain allowlist |
| `SESSION_SECRET` | — | Admin dashboard session secret |
| `SESSION_MAX_AGE_SECS` | — | Admin dashboard session expiry |

### Scheduled Cleanup

| Setting | Default Cron | Description |
|---------|-------------|-------------|
| `CLEAN_CACHE_CRON` | `0 3 * * *` | Cache cleanup (daily at 3:00 AM) |
| `CLEAN_STUCK_PENDING` | `*/10 * * * *` | Stuck-in-queue task cleanup (every 10 minutes) |
| `CLEAN_STUCK_PROCESSING` | `*/10 * * * *` | Stuck-in-processing task cleanup (every 10 minutes) |
| `CLEAN_EXPIRED_FINISHED` | `0 3 * * *` | Expired result cleanup (daily at 3:00 AM) |

### TTL Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `STUCK_QUEUE_SECS` | `600` (10 min) | Timeout threshold for tasks stuck in queue |
| `STUCK_PROCESSING_SECS` | `600` (10 min) | Timeout threshold for tasks stuck during processing |
| `RESULT_EXPIRY_SECS` | `14400` (4 hours) | Retention period for completed task results |

---

## Architecture Overview

### Rendering Flow

```
Request → API Key auth → Look up template → Compute data + template fingerprint
    → Cache hit? → Return cached file directly
    → Cache miss? → Jinja2 render → Write to cache → Return file
```

### Async Task Flow

```
POST /task/{name} → Create task record (SQLite) → Enqueue to asyncio.Queue
Worker coroutine → Dequeue task → Render → Copy result to /result/{task_id}/
Caller → Poll GET /task/file/{task_id} → Download when ready
```

### Template Management

- Templates are stored on the local filesystem (`local` mode) or S3 (`s3` mode)
- Templates are low-write, high-read, highly reusable configuration assets
- The rendering service is a stateless executor — the same input always produces the same output; no automatic versioning is performed
- Consumers manage versioning themselves through naming conventions (e.g., `contract_v2.docx`)

### Image Handling

- Supports two source types: Base64 data URIs and HTTP/HTTPS URLs
- Remote URL images are fetched via `httpx` with configurable timeout
- An optional domain allowlist can restrict remote image sources to prevent SSRF
- Image dimensions are specified via Jinja2 filters within the template, not through the API

### Error Handling

- All errors are returned in RFC 7807 Problem+JSON format
- Template rendering uses a fault-tolerant mode: unmatched variables render as `WARNING: param not found` instead of aborting

### Logging

- Daily rotating log files stored under the `logs/` directory


### Known Issues

- Failing to specify image sizes using {{ image_variable | img(width=x, height=y) }} on image placeholders will result in a corrupted, unopenable .docx file.