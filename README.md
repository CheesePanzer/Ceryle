# Ceryle — 文档渲染服务
https://github.com/CheesePanzer/Ceryle

基于 FastAPI + docxtpl 的自治文档渲染服务，支持将 JSON 数据填入 Word 模板（.docx），自动生成格式化文档。

---

## 功能概述

- **模板渲染**：基于 Jinja2 模板语法，将 JSON 数据填入 Word 模板，生成 .docx 文件
- **图片嵌入**：支持 Base64 编码图片和远程 URL 图片的自动拉取与嵌入，模板内通过 Jinja2 filter 控制图片尺寸: {{ image_variable | img(width=50, height=40) }}
- **缓存机制**：基于请求数据与模板指纹的 SHA-256 哈希缓存，相同输入直接命中缓存，避免重复渲染
- **同步与异步双模式**：小文件可同步直接获取结果；大文件提交异步任务后轮询取件
- **模板管理**：支持模板的上传、下载、列表、删除，存储后端可切换（本地文件系统 / S3）
- **Admin 管理后台**：基于 Web 界面的系统状态监控、模板管理、缓存清理、任务清理

---

## API 接口

所有 API 均以 `/api/v1` 为前缀。除 System 接口外，其余接口均需通过 API Key 认证。

### 认证方式

在请求头中携带 `X-Api-Key`：

```
X-Api-Key: <your-api-key>
```

### System（系统）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查，返回服务状态、版本、时间戳 |
| `GET` | `/` | 重定向至 `/health` |

**`GET /health` 响应示例：**

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

### Render（渲染）

#### 同步渲染

```
POST /api/v1/generate/{template_name}
```

直接渲染模板并返回 .docx 文件流。适用于小文件场景。

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `template_name` | string | 模板文件名（如 `contract.docx`） |

**请求体（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `expectName` | string | 否 | 期望的返回文件名（可含或不含扩展名） |
| `data` | object | 是 | 渲染数据，JSON 对象，键值对应模板中的变量名 |
| `images` | array | 否 | 图片数据列表 |

**图片数据 (`ImageData`) 结构：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `varName` | string | 是 | 模板中对应的图片变量名 |
| `imageSource` | string | 是 | 图片来源：Base64 data URI 或 HTTP/HTTPS URL |
| `realName` | string | 否 | 图片标题/描述 |

**响应头：**

| 响应头 | 说明 |
|--------|------|
| `Content-Disposition` | 文件下载，格式为 `attachment; filename=xxx.docx` |
| `X-File-Hash` | 渲染结果的 SHA-256 哈希 |
| `X-Is-Cache` | `Y` 表示命中缓存，`N` 表示新渲染 |

**请求示例：**

```json
{
  "expectName": "sales_order_2026",
  "data": {
    "customer_name": "张三",
    "order_date": "2026-06-13",
    "items": [
      { "name": "产品A", "qty": 10, "price": 99.00 },
      { "name": "产品B", "qty": 5, "price": 199.00 }
    ],
    "total": 1985.00
  },
  "images": [
    {
      "varName": "company_logo",
      "imageSource": "https://example.com/logo.png",
      "realName": "公司Logo"
    }
  ]
}
```

---

#### 提交异步任务

```
POST /api/v1/task/{template_name}
```

提交渲染任务，立即返回任务 ID。适用于大文件或批量渲染场景。

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `template_name` | string | 模板文件名 |

**请求体：** 同上（`DataRequest`）

**响应：** 返回任务 ID（UUID 字符串），例如 `"550e8400-e29b-41d4-a716-446655440000"`

> 当服务繁忙（队列满）时返回 `429 Too Many Requests`。

---

#### 下载异步任务结果

```
GET /api/v1/task/file/{task_id}
```

根据任务 ID 下载渲染完成的 .docx 文件。

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | UUID | 任务 ID |

**响应：**
- 任务完成：返回 .docx 文件流
- `425 Too Early`：任务尚未完成（pending / running）
- `404 Not Found`：任务不存在
- `500 Internal Server Error`：任务执行失败，响应体中包含错误详情

---

### Management（模板管理）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/templates` | 获取当前模板列表 |
| `POST` | `/api/v1/templates/upload` | 上传新模板 |
| `POST` | `/api/v1/templates/{template_name}/delete` | 删除指定模板 |

#### 获取模板列表

```
GET /api/v1/templates
```

返回所有已注册模板的文件名列表。

#### 上传模板

```
POST /api/v1/templates/upload
```

**表单参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | file | 是 | 模板文件（仅支持 .docx） |
| `overwrite` | bool | 否 | 是否覆盖同名模板，默认 `false` |

> 上传非 .docx 格式文件将返回错误。

#### 删除模板

```
POST /api/v1/templates/{template_name}/delete
```

删除指定模板文件。

---

## Admin 管理后台

Admin 后台位于 `/admin` 路径下，提供 Web 界面进行可视化管理。需要 Session 登录认证。

### 页面功能

| 路径 | 功能 |
|------|------|
| `/admin/login` | 管理员登录 |
| `/admin/` | 仪表盘 —— 查看服务配置、队列状态、任务统计 |
| `/admin/templates` | 模板管理 —— 上传、下载、删除模板 |
| `/admin/tasks` | 任务列表 —— 查看所有任务状态 |
| `/admin/status` | 队列状态 API —— 返回队列长度、Worker 数量、任务统计 |
| `/admin/cache/clear` | 一键清空所有缓存 |
| `/admin/jobs/cleanup-stuck-queue` | 清理卡在队列中超时的任务 |
| `/admin/jobs/cleanup-stuck-processing` | 清理处理中超时的任务 |
| `/admin/jobs/cleanup-expired-results` | 清理过期的已完成任务结果 |

---

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `APP_NAME` | `Ceryle` | 服务名称 |
| `APP_VERSION` | `1.0.0` | 服务版本 |
| `APP_ENV` | `development` | 运行环境（`development` 时开启 Swagger 文档） |
| `API_KEY` | — | API 认证密钥 |
| `WORKER_COUNT` | `1` | 异步渲染 Worker 协程数 |
| `TASK_QUEUE_SIZE` | `50` | 任务队列最大长度，超限返回 429 |
| `STORAGE_BACKEND` | `local` | 模板存储后端：`local` 或 `s3` |
| `TEMPLATE_DIR` | `templates` | 本地模板存储目录 |
| `CACHE_DIR` | `cache` | 缓存目录 |
| `RESULT_DIR` | `result` | 异步任务结果目录 |
| `IMAGE_FETCH_TIMEOUT` | `2` | 远程图片拉取超时（秒） |
| `ALLOWED_IMAGE_DOMAINS` | `[]`（不限制） | 远程图片域名白名单 |
| `SESSION_SECRET` | — | 管理后台 Session 密钥 |
| `SESSION_MAX_AGE_SECS` | — | 管理后台 Session 有效期 |

### 定时清理配置

| 配置项 | 默认 Cron | 说明 |
|--------|-----------|------|
| `CLEAN_CACHE_CRON` | `0 3 * * *` | 缓存清理（每日凌晨 3 点） |
| `CLEAN_STUCK_PENDING` | `*/10 * * * *` | 队列卡住任务清理（每 10 分钟） |
| `CLEAN_STUCK_PROCESSING` | `*/10 * * * *` | 处理中卡住任务清理（每 10 分钟） |
| `CLEAN_EXPIRED_FINISHED` | `0 3 * * *` | 过期结果清理（每日凌晨 3 点） |

### TTL 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `STUCK_QUEUE_SECS` | `600`（10 分钟） | 队列中任务超时阈值 |
| `STUCK_PROCESSING_SECS` | `600`（10 分钟） | 处理中任务超时阈值 |
| `RESULT_EXPIRY_SECS` | `14400`（4 小时） | 已完成任务结果保留时长 |

---

## 架构概要

### 渲染流程

```
请求 → API Key 认证 → 查询模板 → 计算数据+模板指纹
    → 缓存命中？→ 直接返回缓存文件
    → 缓存未命中？→ Jinja2 渲染 → 写入缓存 → 返回文件
```

### 异步任务流程

```
POST /task/{name} → 创建任务记录(SQLite) → 放入 asyncio.Queue
Worker 协程 → 取出任务 → 渲染 → 复制结果到 /result/{task_id}/
调用方 → 轮询 /task/file/{task_id} → 就绪后下载
```

### 模板管理

- 模板存储在本地文件系统（`local` 模式）或 S3（`s3` 模式）
- 模板为低频写、高频读资源，具名管理
- 渲染服务是"无状态执行器"——同一输入始终产生相同输出，不做自动版本管理
- 业务方可自行通过不同文件命名来实现版管理（如 `contract_v2.docx`）

### 图片处理

- 支持 Base64 data URI 和 HTTP/HTTPS URL 两种来源
- 远程 URL 图片通过 `httpx` 拉取，支持超时配置
- 可选域名白名单限制，防止 SSRF
- 图片尺寸由模板内的 Jinja2 filter 指定，不在 API 请求中控制

### 错误处理

- 统一使用 RFC 7807 Problem+JSON 格式返回错误
- Jinja2 模板渲染采用容错模式：未匹配的变量渲染为 `WARNING: param not found`，不中断渲染

### 日志

- 按日滚动日志文件，存储在 `logs/` 目录下

### 已知问题
- File Is not a zip file 报错：docx里面没内容就报这个错
- 必须以单进程模式运行，因为队列无法在进程间共享，从而会导致多进程下管理后台对于队列管理的相关问题
- 如果图片占位符没有使用指定的filter： {{ image_variable | img(width=x, height=y) }}，会导致生成的docx格式损坏，从而无法打开。