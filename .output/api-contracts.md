# 接口契约

> 前端 Mock 和后端实现的唯一对齐依据。任何变更必须同步更新本文件。  
> 定稿日期：2026-08-27

---

## 通用约定

### Base URL

- 开发环境：`http://localhost:8000`
- API 前缀：`/api`

### 认证

- 除 `POST /api/auth/login`、`GET /health` 外，所有接口需在 Header 携带：
  - `Authorization: Bearer <access_token>`

### 统一响应格式

**成功：**

```json
{
  "code": 200,
  "message": "success",
  "data": { }
}
```

**错误：**

```json
{
  "code": 401,
  "message": "未认证或 Token 已过期",
  "data": null
}
```

**分页：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

### HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 通用类型

```typescript
// 用户
interface User {
  id: number
  username: string
  display_name: string
  role: "admin" | "employee"
  employee_id: string
}

// 会话
interface Session {
  id: string
  user_id: number
  title: string
  status: "active" | "ended"
  ended_reason: "completed" | "manual" | null
  message_count: number
  created_at: string  // ISO8601
  updated_at: string
}

// 消息
interface Message {
  id: string
  session_id: string
  role: "user" | "assistant" | "system"
  content: string
  message_type: "text" | "form" | "task" | "reject"
  metadata: Record<string, unknown> | null
  created_at: string
}

// 记忆 KV 项
interface MemoryItem {
  key: string
  value: string
}

// 分页查询参数
interface PageQuery {
  page?: number      // 默认 1
  page_size?: number // 默认 20，最大 100
}
```

---

## 接口清单

### GET /health

**说明：** 健康检查，无需认证。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "ok",
    "version": "1.0.0"
  }
}
```

---

### POST /api/auth/login

**说明：** 用户登录。

**请求体：**

```json
{
  "username": "user_a",
  "password": "usera123"
}
```

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "user": {
      "id": 2,
      "username": "user_a",
      "display_name": "张明",
      "role": "employee",
      "employee_id": "0176338"
    }
  }
}
```

**响应（401）：**

```json
{
  "code": 401,
  "message": "用户名或密码错误",
  "data": null
}
```

---

### POST /api/auth/logout

**说明：** 退出登录（前端清除 Token 即可，后端可选记录）。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": null
}
```

---

### GET /api/auth/me

**说明：** 获取当前登录用户信息。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 2,
    "username": "user_a",
    "display_name": "张明",
    "role": "employee",
    "employee_id": "0176338"
  }
}
```

---

### GET /api/sessions

**说明：** 获取当前用户的会话列表。

**Query：**

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 可选，`active` / `ended` |
| page | number | 默认 1 |
| page_size | number | 默认 20 |

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "sess_001",
        "user_id": 2,
        "title": "神东出差差旅安排",
        "status": "active",
        "ended_reason": null,
        "message_count": 24,
        "created_at": "2026-03-20T09:15:00+08:00",
        "updated_at": "2026-03-20T10:32:00+08:00"
      }
    ],
    "total": 3,
    "page": 1,
    "page_size": 20
  }
}
```

---

### POST /api/sessions

**说明：** 创建新会话。

**请求体：**

```json
{
  "title": "新对话"
}
```

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "sess_new",
    "user_id": 2,
    "title": "新对话",
    "status": "active",
    "ended_reason": null,
    "message_count": 0,
    "created_at": "2026-03-20T11:00:00+08:00",
    "updated_at": "2026-03-20T11:00:00+08:00"
  }
}
```

---

### GET /api/sessions/{session_id}

**说明：** 获取会话详情。

**响应（200）：** 同 Session 对象。

**响应（404）：**

```json
{
  "code": 404,
  "message": "会话不存在",
  "data": null
}
```

---

### PATCH /api/sessions/{session_id}

**说明：** 更新会话（如手动结束）。

**请求体：**

```json
{
  "status": "ended",
  "ended_reason": "manual"
}
```

**响应（200）：** 更新后的 Session 对象。

---

### GET /api/sessions/{session_id}/messages

**说明：** 获取会话消息列表。

**Query：** `page`, `page_size`

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "msg_001",
        "session_id": "sess_001",
        "role": "user",
        "content": "下周三去神东项目出差，帮我安排差旅申请和机票",
        "message_type": "text",
        "metadata": null,
        "created_at": "2026-03-20T09:15:00+08:00"
      },
      {
        "id": "msg_002",
        "session_id": "sess_001",
        "role": "assistant",
        "content": "好的，我已开始为您安排…",
        "message_type": "task",
        "metadata": {
          "task_id": "task_001",
          "progress": "2/4"
        },
        "created_at": "2026-03-20T09:15:05+08:00"
      }
    ],
    "total": 24,
    "page": 1,
    "page_size": 50
  }
}
```

---

### POST /api/sessions/{session_id}/messages

**说明：** 发送用户消息，触发 Agent 回复（支持 SSE 流式，见下方）。

**请求体：**

```json
{
  "content": "经济舱即可，需要订酒店"
}
```

**响应（200，非流式 Mock）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "user_message": { "id": "msg_003", "role": "user", "content": "经济舱即可，需要订酒店", "message_type": "text", "created_at": "..." },
    "assistant_message": {
      "id": "msg_004",
      "role": "assistant",
      "content": "已记录您的偏好。差旅申请已提交…",
      "message_type": "text",
      "metadata": { "sources": [] },
      "created_at": "..."
    }
  }
}
```

**响应（400，已结束会话）：**

```json
{
  "code": 400,
  "message": "会话已结束，无法发送新消息",
  "data": null
}
```

---

### GET /api/sessions/{session_id}/stream

**说明：** SSE 流式获取 Agent 回复（开发阶段可选实现）。

**Query：** `content`（用户消息）

**SSE 事件：**

```
event: delta
data: {"content": "已记录"}

event: done
data: {"message_id": "msg_004", "message_type": "text"}
```

---

### DELETE /api/users/me/memory

**说明：** 清除当前用户长期记忆（对话页「清除记忆」）。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "cleared": true
  }
}
```

---

### GET /api/tasks/{task_id}

**说明：** 获取任务详情（任务详情侧栏）。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "task_001",
    "session_id": "sess_001",
    "goal": "下周三去神东项目出差，安排差旅申请和机票",
    "status": "running",
    "current_step": 2,
    "total_steps": 4,
    "replan_count": 0,
    "steps": [
      {
        "step_id": 1,
        "action": "差旅申请创建",
        "tool": "travel_apply",
        "status": "completed",
        "depends_on": [],
        "params": { "destination": "鄂尔多斯" },
        "result": { "receipt_id": "TA20260325001" }
      },
      {
        "step_id": 2,
        "action": "机票预订",
        "tool": "flight_book",
        "status": "running",
        "depends_on": [1],
        "params": { "cabin": "economy" },
        "result": null
      }
    ],
    "created_at": "2026-03-20T09:15:05+08:00"
  }
}
```

---

### POST /api/tasks/{task_id}/cancel

**说明：** 取消任务。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "task_001",
    "status": "cancelled"
  }
}
```

---

### POST /api/tasks/{task_id}/confirm

**说明：** 用户确认继续（不可逆操作前）。

**请求体：**

```json
{
  "step_id": 4,
  "params": {}
}
```

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "task_001",
    "status": "running",
    "current_step": 4
  }
}
```

---

### PATCH /api/tasks/{task_id}/steps/{step_id}

**说明：** 修改任务步骤参数。

**请求体：**

```json
{
  "params": {
    "destination": "鄂尔多斯",
    "departure_date": "2026-03-26"
  }
}
```

**响应（200）：** 更新后的 Task 对象。

---

### POST /api/forms/{form_type}/preview

**说明：** 生成/刷新业务表单预览。`form_type`: `email` | `meeting` | `travel` | `workpackage`

**请求体：**

```json
{
  "session_id": "sess_001",
  "task_id": "task_001",
  "fields": {}
}
```

**响应（200，差旅示例）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "form_id": "form_001",
    "form_type": "travel",
    "status": "preview",
    "fields": {
      "destination": "鄂尔多斯",
      "departure_date": "2026-03-26",
      "return_date": "2026-03-28",
      "project": "神东能源数据治理平台",
      "transport": "飞机 · 经济舱",
      "description": "现场培训"
    }
  }
}
```

---

### POST /api/forms/{form_id}/confirm

**说明：** 确认表单（预览 → 确认态）。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "form_id": "form_001",
    "status": "confirmed"
  }
}
```

---

### POST /api/forms/{form_id}/submit

**说明：** 提交表单。

**请求体：**

```json
{
  "fields": {
    "destination": "鄂尔多斯",
    "departure_date": "2026-03-26"
  }
}
```

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "form_id": "form_001",
    "status": "submitted",
    "receipt_id": "RC20260325001",
    "message": "差旅申请已进入审批流程"
  }
}
```

---

### GET /api/forms/{form_id}/receipt

**说明：** 获取提交回执。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "receipt_id": "RC20260325001",
    "status": "submitted",
    "summary": "差旅申请已进入审批流程",
    "submitted_at": "2026-03-20T10:00:00+08:00"
  }
}
```

---

### GET /api/knowledge/qa

**说明：** 员工知识库帮助 — QA 列表（只读）。

**Query：** `keyword`, `page`, `page_size`

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "qa_001",
        "question": "鄂尔多斯住宿费标准是多少？",
        "answer": "其他人员不超过300元/天",
        "source_clause": "差旅管理办法·第十二条",
        "document_name": "国家能源集团差旅管理办法2024修订版.pdf"
      }
    ],
    "total": 50,
    "page": 1,
    "page_size": 20
  }
}
```

---

### GET /api/knowledge/documents

**说明：** 员工知识库帮助 — 文档列表（只读）。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "doc_001",
        "filename": "国家能源集团差旅管理办法2024修订版.pdf",
        "file_type": "pdf",
        "updated_at": "2026-03-01T00:00:00+08:00"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20
  }
}
```

---

### GET /api/knowledge/documents/{document_id}/download

**说明：** 下载政策文档。

**响应：** 文件流（`Content-Type: application/pdf` 等）。

---

### GET /api/knowledge/search

**说明：** 员工知识库帮助 — 统一搜索 QA 与文档。

**Query：** `q`（必填）

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "qa_results": [],
    "document_results": []
  }
}
```

---

### GET /api/admin/documents

**说明：** 管理员 — 文档列表。

**权限：** `admin`

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "doc_001",
        "filename": "国家能源集团差旅管理办法2024修订版.pdf",
        "file_type": "pdf",
        "status": "ready",
        "uploaded_by": "admin",
        "created_at": "2026-03-01T00:00:00+08:00"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  }
}
```

---

### POST /api/admin/documents

**说明：** 管理员 — 上传文档（multipart/form-data）。

**请求：** `file`（PDF/Word）

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "doc_002",
    "filename": "差旅报销实施细则.docx",
    "status": "uploading",
    "progress": {
      "stage": "uploading",
      "percent": 0
    }
  }
}
```

---

### GET /api/admin/documents/{document_id}/progress

**说明：** 上传/解析/入库进度。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "doc_002",
    "status": "indexing",
    "progress": {
      "stage": "indexing",
      "percent": 67
    }
  }
}
```

---

### DELETE /api/admin/documents/{document_id}

**说明：** 管理员 — 删除文档及关联 QA。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": { "deleted": true }
}
```

---

### GET /api/admin/qa

**说明：** 管理员 — QA 列表。

**Query：** `keyword`, `page`, `page_size`

**响应（200）：** 同知识库 QA 结构，含 `document_id`。

---

### POST /api/admin/search-test

**说明：** 管理员 — 检索测试。

**请求体：**

```json
{
  "query": "鄂尔多斯住宿费标准是多少"
}
```

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "results": [
      {
        "type": "qa",
        "question": "鄂尔多斯住宿费标准是多少？",
        "answer": "其他人员不超过300元/天",
        "similarity": 0.92,
        "source_clause": "差旅管理办法·第十二条"
      }
    ]
  }
}
```

---

### GET /api/admin/conversations/stats

**说明：** 管理员 — 对话监控统计。

**权限：** `admin`

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total_sessions": 1248,
    "active_sessions": 36,
    "today_new_sessions": 89
  }
}
```

---

### GET /api/admin/conversations

**说明：** 管理员 — 对话监控会话列表。

**Query：** `keyword`, `status`, `page`, `page_size`

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "sess_001",
        "user": {
          "display_name": "张明",
          "employee_id": "0176338"
        },
        "title": "神东出差差旅安排",
        "status": "active",
        "message_count": 24,
        "created_at": "2026-03-20T09:15:00+08:00",
        "updated_at": "2026-03-20T10:32:00+08:00"
      }
    ],
    "total": 1248,
    "page": 1,
    "page_size": 20
  }
}
```

---

### GET /api/admin/conversations/export

**说明：** 管理员 — 导出会话记录（Mock 返回下载 URL 或 CSV 流）。

**Query：** 同列表筛选参数

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "download_url": "/api/admin/conversations/export/file?token=xxx"
  }
}
```

---

### GET /api/admin/settings

**说明：** 管理员 — 获取系统配置。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "system_name": "智能办公助手 · 国能集团",
    "welcome_message": "您好，我是智能办公助手，有什么可以帮您？",
    "default_model": "qwen-max",
    "temperature": 0.7,
    "session_retention_days": 90,
    "max_concurrent_sessions": 3,
    "log_level": "INFO",
    "api_timeout_seconds": 60
  }
}
```

---

### PUT /api/admin/settings

**说明：** 管理员 — 保存系统配置。

**请求体：** 同 GET 响应 `data` 结构（部分字段可选）。

**响应（200）：** 更新后的配置对象。

---

### GET /api/settings/profile

**说明：** 个人设置 — 账号信息。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "username": "user_a",
    "display_name": "张明",
    "role": "employee",
    "employee_id": "0176338"
  }
}
```

---

### PATCH /api/settings/theme

**说明：** 个人设置 — 更新主题。

**请求体：**

```json
{
  "theme": "light"
}
```

`theme`: `light` | `dark` | `system`

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "theme": "light"
  }
}
```

---

### GET /api/settings/version

**说明：** 个人设置 — 版本信息。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "version": "1.0.0",
    "release_date": "2026-03-20",
    "has_update": false,
    "changelog": [
      {
        "version": "1.0.0",
        "date": "2026-03-20",
        "items": [
          "首次发布：对话、知识库、差旅/工包/会议/邮件工具",
          "支持个人设置与长期记忆",
          "人工协助 Mock 工单"
        ]
      }
    ]
  }
}
```

---

### POST /api/settings/version/check

**说明：** 检查更新（Mock）。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "has_update": false,
    "message": "已是最新版本"
  }
}
```

---

### GET /api/settings/memory

**说明：** 个人设置 — 获取长期记忆配置与已提取字段。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "memory_enabled": true,
    "structured": {
      "employee_id": "0176338",
      "department": "神东煤炭集团",
      "position": "员工",
      "email": "zhangming@ceic.com",
      "travel_mode_preference": "经济舱",
      "related_projects": ["神东能源数据治理平台"],
      "gender": "unknown"
    },
    "memory_items": [
      { "key": "常用出差目的地", "value": "鄂尔多斯、北京" },
      { "key": "常用联系人", "value": "李经理（工包审批）" },
      { "key": "默认部门", "value": "神东煤炭集团" },
      { "key": "沟通偏好", "value": "简洁回复，优先表格展示" },
      { "key": "差旅偏好", "value": "优先下午航班，经济舱" }
    ]
  }
}
```

---

### PATCH /api/settings/memory

**说明：** 个人设置 — 更新记忆开关或编辑记忆字段。

**请求体：**

```json
{
  "memory_enabled": true,
  "memory_items": [
    { "key": "常用出差目的地", "value": "鄂尔多斯、北京、上海" },
    { "key": "沟通偏好", "value": "简洁回复" }
  ]
}
```

**响应（200）：** 更新后的完整 memory 对象（同 GET）。

---

### POST /api/tickets

**说明：** 提交人工协助 Mock 工单。

**请求体：**

```json
{
  "session_id": "sess_001",
  "title": "差旅订票失败需人工协助",
  "description": "Agent 重规划 3 次后仍无法预订周三下午航班，请协助处理"
}
```

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "WO20260325001",
    "session_id": "sess_001",
    "title": "差旅订票失败需人工协助",
    "description": "Agent 重规划 3 次后仍无法预订周三下午航班，请协助处理",
    "status": "pending",
    "created_at": "2026-03-20T11:30:00+08:00"
  }
}
```

---

### GET /api/tickets/{ticket_id}

**说明：** 查询工单状态。

**响应（200）：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "WO20260325001",
    "status": "pending",
    "title": "差旅订票失败需人工协助",
    "created_at": "2026-03-20T11:30:00+08:00"
  }
}
```

---

## 错误码补充

| code | 说明 |
|------|------|
| 400 | 参数错误、业务规则不满足（如已结束会话发消息） |
| 401 | 未登录或 Token 无效 |
| 403 | 无管理员权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
