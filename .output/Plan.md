# 开发计划

> 设计阶段与开发阶段的衔接文件。所有开发进度以本文件为准。  
> 生成日期：2026-08-27 · 原型审核已通过

---

## 一、功能清单总览

| 序号 | 功能名称 | 一句话描述 | 对应页面 | 优先级 | 状态 |
|------|---------|-----------|---------|--------|------|
| F01 | 用户登录 | 账号密码登录，按角色进入系统 | 登录页 | MVP | 前端完成 |
| F02 | 员工对话 | 自然语言对话、历史会话、清记忆 | 员工对话页 | MVP | 前端完成 |
| F03 | 任务详情 | 查看 Agent 任务进度与步骤 | 任务详情侧栏 | MVP | 前端完成 |
| F04 | 业务表单 | 差旅/工包/会议/邮件 预览→确认→回执 | 业务表单侧栏 | MVP | 前端完成（差旅） |
| F05 | 知识库管理 | 上传文档、QA 管理、检索测试 | 管理后台 | MVP | 前端完成 |
| F06 | 知识库帮助 | 员工浏览 QA 与政策文档 | 知识库帮助页 | MVP | 前端完成 |
| F07 | 个人设置 | 主题/账号/版本/记忆（含编辑） | 个人设置 4 Tab | MVP | 前端完成 |
| F08 | 人工协助 | Mock 工单提交与查询 | 对话内弹窗 | MVP | 前端完成 |
| F09 | 对话监控 | 管理员查看会话统计与列表 | 对话监控页 | MVP | 前端完成 |
| F10 | 系统设置 | 管理员配置系统与模型参数 | 系统设置页 | MVP | 前端完成 |

---

## 二、数据契约摘要

> 完整数据契约见 [PRD.md](./PRD.md) 第 8 章；接口契约见 [api-contracts.md](./api-contracts.md)

### 统一响应格式

- 成功：`{"code": 200, "message": "success", "data": { ... }}`
- 错误：`{"code": <错误码>, "message": "<描述>", "data": null}`
- 分页：`{"code": 200, "data": {"items": [...], "total": N, "page": N, "page_size": N}}`

### 关键业务实体

| 实体 | 核心字段 |
|------|---------|
| User | id, username, role, display_name, employee_id |
| Session | id, user_id, title, status, message_count |
| Message | id, session_id, role, content, message_type, metadata |
| Task | id, session_id, goal, status, steps[] |
| Form | form_id, form_type, status, fields |
| Document | id, filename, status, uploaded_by |
| QA | id, question, answer, source_clause |
| MemoryItem | key, value（+ structured 画像字段） |
| Ticket | id, title, description, status |
| SystemConfig | system_name, default_model, temperature 等 |

---

## 三、前端开发清单

| 序号 | 页面/组件 | 涉及功能 | Mock 数据来源 | 状态 |
|------|----------|---------|--------------|------|
| P01 | 登录页 | F01 | POST /api/auth/login | ✅ 已完成 |
| P02 | 员工对话页 | F02, F08 | sessions, messages, tickets | ✅ 已完成 |
| P03 | 任务详情侧栏 | F03 | GET /api/tasks/{id} | ✅ 已完成 |
| P04 | 业务表单侧栏 | F04 | forms preview/confirm/submit/receipt | ✅ 已完成（差旅） |
| P05 | 知识库管理 | F05 | admin/documents, qa, search-test | ✅ 已完成 |
| P06 | 知识库帮助 | F06 | knowledge/qa, documents | ✅ 已完成 |
| P07 | 个人设置（4 Tab） | F07 | settings/theme, version, memory | ✅ 已完成 |
| P08 | 人工协助弹窗 | F08 | POST /api/tickets | ✅ 已完成 |
| P09 | 对话监控 | F09 | admin/conversations | ✅ 已完成 |
| P10 | 系统设置 | F10 | admin/settings | ✅ 已完成 |

**Mock 数据目录：** `frontend/src/mocks/`（格式严格遵守 api-contracts.md）

**路由规划：**

| 路由 | 页面 |
|------|------|
| `/login` | P01 |
| `/chat` | P02 |
| `/help/knowledge` | P06 |
| `/settings` | P07（子路由：theme / account / version / memory） |
| `/admin/knowledge` | P05 |
| `/admin/conversations` | P09 |
| `/admin/settings` | P10 |

### 前端验收标准

- [x] 所有页面 UI 与 `.output/prototypes/原型汇总.pen` 一致（含对话监控详情弹窗）
- [x] 所有页面使用 Mock 数据可正常交互
- [x] Mock 数据格式与 api-contracts.md 完全一致
- [x] 管理后台仅 admin 角色可访问
- [x] 已结束会话输入框 disabled
- [x] 记忆设置 Tab：开关 ON 时展示可编辑记忆字段
- [x] **用户验收通过**（2026-08-27）

> 前端验收已通过，进入后端开发。

---

## 四、后端开发清单

### Python 环境

- **Python 指令**：`python3`（3.14.3，已确认）
- **虚拟环境**：`.venv`（位于 `backend/` 下）
- [x] 用户已确认 Python 指令
- [x] 用户已确认虚拟环境名称
- [x] 用户已确认 `backend/config/app.toml` 配置项（DashScope API Key 已配置）

| 序号 | 功能 | 依赖 | 对应接口 | 状态 |
|------|------|------|---------|------|
| B00 | 基础设施 | 无 | GET /health | 代码完成，待用户测试 |
| B01 | 用户登录与鉴权 | B00 | auth/login, auth/me | 代码完成，待用户测试 |
| B02 | 会话与消息 CRUD | B01 | sessions/* | 已完成（含前端联调切换） |
| B03 | Agent 对话与流式回复 | B02 | messages, stream | 已完成（POST 联调 + SSE） |
| B04 | 任务与工作记忆 | B03 | tasks/* | 待开发 |
| B05 | 业务表单 Mock | B03 | forms/* | 待开发 |
| B06 | 知识库上传与索引 | B01 | admin/documents | 待开发 |
| B07 | RAG 检索与问答 | B06 | knowledge/*, search-test | 待开发 |
| B08 | 长期记忆读写 | B02 | settings/memory, DELETE memory | 待开发 |
| B09 | 个人设置 | B01 | settings/theme, version | 待开发 |
| B10 | Mock 工单 | B02 | tickets/* | 待开发 |
| B11 | 对话监控 | B02 | admin/conversations | 待开发 |
| B12 | 系统设置 | B01 | admin/settings | 待开发 |

> 每个功能开发前须在本文件对应功能下方写入分层实现思路；完成后更新状态并提供测试指令。

---

## 五、开发顺序建议

### 阶段 1：前端（Mock 驱动）

1. P01 登录页 → P02 员工对话页（核心）
2. P03 任务详情 + P04 业务表单（四类 Tab 变体）
3. P07 个人设置（4 Tab）
4. P06 知识库帮助
5. P05 / P09 / P10 管理后台三页
6. P08 人工协助弹窗
7. **用户前端验收**

### 阶段 2：后端（逐功能）

1. B00 → B01 → B02（基础设施 + 鉴权 + 会话）
2. B08 + B09（设置与记忆，联调 P07）
3. B06 + B07（知识库 + RAG，联调 P05/P06）
4. B03 + B04 + B05（Agent 核心，联调 P02/P03/P04）
5. B10 + B11 + B12（工单 + 管理后台）
6. Mock 切换为真实 API，全链路测试

---

## 六、功能详情（开发时逐个展开）

> 以下内容在开发每个功能时由 feature-plan 写入。

### B00：基础设施

**分层实现思路（feature-plan）：**

```
models/common.py     → ApiResponse[T]、HealthData（对齐 api-contracts code/message/data 格式）
config/settings.py   → AppSettings（database_url, host, port, cors_origins, secret_key, debug）
db/session.py        → async SQLAlchemy engine + get_session + init_db/close_db
db/models.py         → Base（DeclarativeBase，B01 起扩展 User 等表）
api/responses.py     → success()/error()/paginated() 辅助函数
api/routes/health.py → GET /health
main.py              → APIServer 注册路由、生命周期钩子、Logger 初始化
config/app.toml      → 默认配置（含 config.example.toml 模板）
requirements.txt     → fastapi, uvicorn, sqlalchemy, aiosqlite, pydantic, python-jose, passlib 等
```

**交付标准：**
- [x] `GET /health` 返回 `{"code":200,"message":"success","data":{"status":"ok","version":"1.0.0"}}`
- [x] SQLite 连接可初始化（空库，表结构 B01 起建）
- [x] CORS 允许 `http://localhost:5173`
- [ ] 用户测试通过

**建议配置项（`backend/config/app.toml`）：**

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| debug | true | 开发模式 |
| secret_key | change-me | JWT 签名（B01 用） |
| database_url | sqlite+aiosqlite:///../data/sqlite/app.db | SQLite 路径 |
| host | 0.0.0.0 | 服务地址 |
| port | 8000 | 服务端口 |
| cors_origins | ["http://localhost:5173"] | 前端跨域 |
| llm_api_key | （空） | 阿里云百炼 DashScope API Key |
| llm_base_url | https://dashscope.aliyuncs.com/compatible-mode/v1 | OpenAI 兼容接口地址 |
| llm_model | qwen-max | 默认模型（可选 qwen-plus / qwen-turbo / qwen-long） |
| llm_temperature | 0.7 | 回复随机性 |
| llm_timeout_seconds | 60 | API 超时（秒） |
| llm_max_tokens | 4096 | 单次最大输出 token |
| secret_key | （本地配置） | JWT 签名密钥 |

**测试指令（B00）：**

```bash
# 1. 创建虚拟环境（在 backend/ 目录）
cd backend
python3.11 -m venv .venv    # 若无 python3.11，改用 python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
python -m pip install -r requirements.txt

# 3. 启动后端（PYTHONPATH=../.. 引入上级目录的 pycore）
PYTHONPATH=../.. python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 4. 健康检查
curl http://localhost:8000/health
# 预期：{"code":200,"message":"success","data":{"status":"ok","version":"1.0.0"}}
```

### B01：用户登录与鉴权

**分层实现思路：**

```
db/user_model.py       → User ORM（username, hashed_password, display_name, role, employee_id）
models/user.py         → LoginRequest, LoginData, UserPublic
core/security.py       → bcrypt 哈希/校验
core/jwt.py            → JWT 签发与解析
repositories/user.py   → get_by_username, get_by_id, create, count
services/auth.py       → login, get_current_user
db/seed.py             → 启动时写入 admin/user_a/user_b（与 Mock 一致）
api/deps.py            → get_current_user（Bearer Token）
api/routes/auth.py     → POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me
main.py                → 注册 auth 路由 + HTTPException 统一错误格式
frontend/vite.config   → /api 代理到 localhost:8000
```

**测试账号（种子数据）：** admin/admin123、user_a/usera123、user_b/userb123

**测试指令（B01）：**

```bash
# 终端
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 前端联调：frontend/.env 设置 VITE_USE_MOCK=false，VITE_API_BASE_URL=/api
# 启动后端 + 前端后，登录页使用 admin/admin123
```

### 架构决策（已确认）

| 项 | 决策 |
|---|---|
| Embedding | 本地 `BAAI/bge-small-zh-v1.5`（sentence-transformers） |
| 大模型 | 阿里云百炼 DashScope（qwen-max） |
| 系统 Prompt / 拒识 | 按 PRD 5.1 默认，见 `backend/src/agent/prompts.py` |

### B02：会话与消息

**分层实现思路：**

```
db/chat_models.py        → SessionRecord, MessageRecord ORM
models/session.py        → SessionPublic, MessagePublic, SessionCreate/Update
repositories/session.py  → 会话与消息 CRUD + 分页
services/session.py      → 业务逻辑、用户隔离、发消息占位回复（B03 替换为 Agent）
api/routes/sessions.py   → GET/POST /api/sessions, GET/PATCH /{id}, messages CRUD
db/seed.py               → user_a 演示会话 sess_001/sess_002
agent/prompts.py         → 系统 Prompt、拒识话术（B03 使用）
```

**接口：** `GET/POST /api/sessions`、`GET/PATCH /api/sessions/{id}`、`GET/POST .../messages`

**测试指令（B02）：**

```bash
# 1. 登录获取 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user_a","password":"usera123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 2. 会话列表
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/sessions

# 3. 发消息
curl -X POST http://localhost:8000/api/sessions/sess_001/messages \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content":"测试消息"}'
```

### B03：Agent 对话

**分层实现思路：**

```
integrations/llm_factory.py  → DashScope OpenAI 兼容客户端（trust_env=False）
agent/chat_plugin.py         → ChatAgentPlugin（BasePlugin + LLM 调用）
agent/prompts.py             → 系统 Prompt、拒识话术（PRD 5.1）
services/agent.py            → AgentService 编排
services/session.py          → send_message / stream_reply 接入 Agent
api/routes/sessions.py       → POST messages（同步）+ GET stream（SSE）
```

**行为说明：**
- 发送消息 → DashScope `qwen-max` 生成回复（含完整会话上下文，最多 30 条）
- 超出七大场景 → 模型按拒识话术回复（`message_type: reject`）
- LLM 失败 → 降级固定话术，不抛 500
- SSE：`GET /api/sessions/{id}/stream?content=...`

**测试指令（B03）：**

```bash
# 同步（前端默认走此接口）
curl -X POST http://localhost:8000/api/sessions/sess_001/messages \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content":"鄂尔多斯出差住宿费标准是多少？"}'

# 拒识测试
curl -X POST ... -d '{"content":"帮我写一段 Python 爬虫"}'

# SSE 流式
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/sessions/sess_001/stream?content=你好"
```

### B04：任务与工作记忆

（待开发时补充）

### B05：业务表单 Mock

（待开发时补充）

### B06：知识库上传与索引

（待开发时补充）

### B07：RAG 检索与问答

（待开发时补充）

### B08：长期记忆

（待开发时补充）

### B09：个人设置

（待开发时补充）

### B10：Mock 工单

（待开发时补充）

### B11：对话监控

（待开发时补充）

### B12：系统设置

（待开发时补充）

---

## 七、原型与设计参考

| 文件 | 用途 |
|------|------|
| `.output/prototypes/原型汇总.pen` | 全部页面视觉原型（审核已通过） |
| `.output/PRD.md` | 产品需求定稿 |
| `.output/api-contracts.md` | 接口契约 |

---

## 八、变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-27 | 阶段 C 初始化：原型审核通过，生成本开发计划 |
| 2026-08-27 | 前端启动：初始化 Vue3 项目，完成 P01/P02/P07/P08，管理后台与帮助页骨架 |
| 2026-08-27 | 前端续开发：P03 任务侧栏、P04 差旅表单、P05/P06/P09/P10 完整 Mock 页 |
| 2026-08-27 | B03 Agent 对话：DashScope LLM + 拒识策略 + SSE 流式 |
