# 简历生成与公司推荐系统

> 多用户 Web 应用 + 用户自配 LLM API
> 架构参照 `D:\recipe-recommender`
> 设计冻结日期：2026-06-09

---

## 1. 目标与范围

帮求职用户解决两件事：(1) 根据结构化的过往经历 + 求职意向，生成一份**定向优化的简历**；(2) 给出**推荐投递的公司**与**简历/能力上需要完善的点**。多用户，每人用账号密码登录，自行配置 LLM API key 并选择模型。

### 1.1 In Scope
- 多用户：账号密码注册 / 登录（JWT）
- 每用户配置 LLM：provider（Gemini / OpenAI 兼容）+ API key（加密存储）+ 拉取并选择模型
- 简历主档维护（结构化表单：基本信息 / 教育 / 工作 / 项目 / 技能 / 自评）
- 按求职意向生成：定制简历 + 推荐公司 + 完善点（单次 LLM 调用返回三部分）
- 生成结果历史记录与回看
- 简历导出：网页结构化预览 + 复制/下载 Markdown + 浏览器打印为 PDF
- LLM 失败 / 配额降级处理
- 本地 SQLite 运行；Vercel + Postgres(Neon) 部署，同套代码自动切换

### 1.2 Out of Scope（v1 不做）
- 真实招聘网站 / 岗位 API 接入（公司推荐为纯 LLM 生成）
- Word(.docx) 导出
- 邀请码注册门槛（注册开放）
- 简历模板多套切换 / 富文本排版编辑器
- 多语言简历（中文为主）
- 简历图片 / 头像上传
- 团队协作 / 分享

### 1.3 运行前提
- 用户自备可访问对应 LLM 服务（Gemini 或 OpenAI 兼容端点）的 API key
- 本机 Python 3.10+（本地运行）
- 现代浏览器（打印为 PDF 依赖浏览器自带能力）

---

## 2. 技术栈与架构

### 2.1 技术栈

| 层 | 技术 | 选型理由 |
|---|---|---|
| 后端 | Python 3.10+ / FastAPI | async、自动 OpenAPI、对 LLM 集成友好；与参考项目一致 |
| 数据库 | SQLite 本地单文件 / Postgres(Neon) 部署 | SQLAlchemy 2.0，URL 自动切换驱动 |
| LLM 客户端 | `google-genai`（Gemini）+ httpx（OpenAI 兼容） | 复用参考项目的 provider 抽象 |
| 认证 | bcrypt 密码哈希 + python-jose JWT | 复用参考项目 auth |
| 密钥加密 | cryptography Fernet | API key 加密落库，复用参考 crypto |
| 前端 | 单页 HTML + Vue 3（CDN）+ 原生 fetch | 零构建、零 npm |
| 配置 | `.env` + python-dotenv | 密钥/DB URL 不进 git |
| 测试 | pytest + httpx | 与参考一致 |
| 部署 | Vercel `@vercel/python` | `api/index.py` 复用 |

### 2.2 架构

```
浏览器 (Vue 3 CDN SPA, localhost:8000 / Vercel)
   │  HTML + Vue + fetch (Authorization: Bearer <JWT>)
   ▼
FastAPI 服务 (uvicorn 本地 / @vercel/python 部署)
   │
   ├─ routes/auth.py          注册 / 登录 → JWT
   ├─ routes/llm_config.py    每用户 provider + API key(加密) + 选模型   ← 复用
   ├─ routes/profile.py       简历主档 CRUD（结构化）
   ├─ routes/generate.py      POST /api/generate（核心）
   ├─ routes/runs.py          历史生成记录
   │
   ├─ services/auth.py        bcrypt + JWT + current_user 依赖           ← 复用
   ├─ services/crypto.py      Fernet 加解密                              ← 复用
   ├─ services/llm/           base/factory/gemini_provider/openai_compat/service ← 复用
   ├─ services/resume.py      主档→Markdown 渲染、字段合并/裁剪
   ├─ services/quota.py       每用户每日配额                            ← 复用
   │
   └─ db/  models.py session.py init.py    SQLite/Postgres 自动切换
   │
   ▼
用户配置的 LLM API（Gemini / OpenAI 兼容端点）
```

启动：
```bash
uvicorn app.main:app --reload --port 8000   # 浏览器开 http://localhost:8000
```

---

## 3. 数据模型

多用户，所有业务表带 `user_id`。复用参考项目的 `users`、`llm_config`、`api_quota`（原样）。

### 3.1 `users`（复用）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| username | TEXT UNIQUE | |
| password_hash | TEXT | bcrypt |
| created_at | TIMESTAMP | |

> 注册开放，无邀请码（不引入参考项目的 `invite_codes` 表）。

### 3.2 `llm_config`（复用）
| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | UUID PK | |
| provider | TEXT | `gemini` / `openai_compat` |
| api_key_encrypted | TEXT NULL | Fernet 密文 |
| base_url | TEXT NULL | OpenAI 兼容端点 |
| model | TEXT NULL | 选中的模型 |
| updated_at | TIMESTAMP | |

### 3.3 `resume_profile`（简历主档，每用户一行）
| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | UUID PK | |
| basic_info | JSON | `{name, phone, email, city, status, links[]}` |
| educations | JSON[] | `[{school, major, degree, start, end, highlights}]` |
| experiences | JSON[] | `[{company, title, start, end, description}]` |
| projects | JSON[] | `[{name, role, tech_stack, description, outcome}]` |
| skills | JSON[] | `["Python","React",...]` |
| self_summary | TEXT | 自我评价，可空 |
| updated_at | TIMESTAMP | |

### 3.4 `resume_run`（一次「求职意向→生成」记录）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| user_id | UUID FK → users.id, index | |
| target_role | TEXT | 目标岗位（必填） |
| target_industry | TEXT NULL | 目标行业 |
| target_city | TEXT NULL | 目标城市 |
| work_type | TEXT NULL | 全职/实习/远程等 |
| salary_expect | TEXT NULL | 薪资期望 |
| notes | TEXT NULL | 补充说明 |
| tailored_resume | JSON | LLM 生成的定制简历（结构化，见 §4.3） |
| recommendations | JSON[] | `[{company, type, reason, suggested_role}]` |
| gaps | JSON[] | `[{gap, importance, suggestion}]` |
| model_used | TEXT | 实际使用的模型 |
| created_at | TIMESTAMP, index | |

### 3.5 `api_quota`（复用，每用户每日防呆配额）
| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | UUID PK | |
| quota_date | DATE PK | UTC+8 当日 |
| count | INTEGER | 当日生成调用次数 |

每日上限来自 `DAILY_GENERATE_QUOTA`（默认 50，防 bug 死循环，非成本控制）。超限静默拒绝并提示。

---

## 4. 核心流程

### 4.1 认证

- `POST /api/auth/register` body `{username, password}`：用户名唯一校验 → bcrypt 哈希 → 建用户 → 返回 JWT
- `POST /api/auth/login` body `{username, password}`：校验 → 返回 JWT
- 其余业务接口经 `current_user` 依赖解析 `Authorization: Bearer <JWT>`
- 密码长度 ≤ 72 字节（bcrypt 限制），Pydantic 校验

### 4.2 简历主档 CRUD `/api/profile`

- `GET /api/profile`：返回当前用户主档（无则返回空结构）
- `PUT /api/profile` body：整档 upsert（主键为 user_id）
- 前端按区块编辑，提交整档。校验在边界进行（必填基本信息姓名）。

### 4.3 生成 `POST /api/generate`（核心）

body：`{target_role, target_industry?, target_city?, work_type?, salary_expect?, notes?}`

```
1. 读 resume_profile
   主档为空（无姓名 / 教育与工作均空）→ 返回 { error: "PROFILE_EMPTY" }，不调 LLM
2. 取 llm_config → 构造 provider（factory）
   无 api_key → 返回 { error: "LLM_NOT_CONFIGURED" }
3. 配额检查：api_quota.today() >= DAILY_GENERATE_QUOTA → { error: "QUOTA_EXCEEDED" }
4. 构造 prompt（generate.txt），传 [主档 + 求职意向]，要求严格 JSON：
   { tailored_resume: {...}, recommendations: [...], gaps: [...] }
   —— 单次调用保证三部分一致；省配额
5. provider.generate(prompt, timeout=15s)
   宽松解析 parse_llm_json；失败 → temperature+0.2 重试 1 次；仍失败 → { error: "PARSE_FAILED" }
6. 校验三部分结构齐全；缺失部分置空数组并标 warning
7. api_quota.increment(today)
8. 落库 resume_run；返回 { run_id, tailored_resume, recommendations, gaps, model_used, warning? }
```

`tailored_resume` 结构（与主档同构，便于前端复用渲染 + 导出）：
```json
{
  "basic_info": {...},
  "summary": "针对目标岗位重写的一段概述",
  "educations": [...],
  "experiences": [{"company":"","title":"","start":"","end":"","bullets":["量化业绩1","..."]}],
  "projects": [...],
  "skills": ["..."]
}
```

`recommendations` 项：`{company, type, reason, suggested_role}`
`gaps` 项：`{gap, importance("高"/"中"/"低"), suggestion}`

### 4.4 历史记录 `/api/runs`

- `GET /api/runs`：当前用户的生成记录列表（按 created_at 倒序，含摘要字段）
- `GET /api/runs/{id}`：单条完整结果
- `GET /api/runs/{id}/markdown`：返回该次定制简历的 Markdown 文本（供复制/下载）

### 4.5 LLM 配置 `/api/llm-config`（复用参考交互）

- `GET`：返回当前配置（脱敏，仅末 4 位）
- `PUT`：保存 provider/base_url/model/api_key（加密）
- `POST /models`：用当前/新 key 拉取可用模型列表供前端下拉选择

### 4.6 Prompt 设计（`app/prompts/generate.txt`）

要点：
- 角色：资深简历顾问 + 职业规划师
- 输入：主档全部字段 + 求职意向各字段
- 输出严格 JSON，三部分：
  - `tailored_resume`：突出与目标岗位相关的经历，业绩量化，重写 summary
  - `recommendations`：3–6 家匹配公司/公司类型，含匹配理由与建议岗位（明确说明为 AI 推断，非实时招聘数据）
  - `gaps`：3–6 条完善点，含重要度与可执行改进建议
- 禁止编造用户没有的事实经历（定制 = 重排/强调/措辞优化，不得虚构）

---

## 5. 错误处理（静默降级哲学）

| 失败点 | 处理 |
|---|---|
| 主档为空 | `PROFILE_EMPTY`，前端引导去填主档；不调 LLM |
| 未配置 LLM key | `LLM_NOT_CONFIGURED`，引导去 AI 设置 |
| LLM 超时/网络 | 15s 超时，返回友好 warning，不落库 |
| LLM 返回非 JSON | 宽松解析（截首个 `{` 到末尾 `}`）→ temp+0.2 重试 1 次 → 仍失败 `PARSE_FAILED` 提示重试 |
| 三部分某部分缺失 | 该部分置空 + warning，其余照常返回 |
| 每日配额用尽 | `QUOTA_EXCEEDED` + 友好提示，明日恢复 |
| 重复用户名注册 | 409 友好提示 |
| 无效/过期 JWT | 401 |
| 保存的 key 解密失败（LLM_ENC_KEY 轮换） | 提示重新输入 key |

---

## 6. 前端（单页 Vue 3 CDN，零构建）

`static/index.html` + `static/app.js` + `static/style.css`。Token 存 localStorage，fetch 统一带 Bearer。

页面/视图：
1. **登录 / 注册**
2. **简历主档**：分区块表单（基本信息 / 教育[] / 工作[] / 项目[] / 技能[] / 自评），条目可增删；保存整档
3. **AI 设置**：provider 切换、API key 输入、`拉取模型`按钮 → 下拉选模型、保存
4. **生成**：求职意向表单 → 「生成」→ 三栏结果：
   - 定制简历预览卡（结构化排版）
   - 推荐公司列表（公司/类型/理由/建议岗位）
   - 完善点清单（按重要度着色）
5. **历史**：生成记录列表，点击回看

导出（简历预览卡操作区）：
- 「复制 Markdown」/「下载 .md」：调用 `GET /api/runs/{id}/markdown`，Blob 下载或写剪贴板
- 「打印 / 存为 PDF」：`window.print()`，`@media print` 仅显示简历预览区、隐藏导航与其它栏

> Markdown 渲染逻辑放后端 `services/resume.py`（逻辑集中、可单测），通过 `/api/runs/{id}/markdown` 暴露。

---

## 7. 目录结构

```
D:\Resume_Generator\
├── app\
│   ├── main.py                FastAPI 入口，挂 routes + 静态文件
│   ├── config.py              .env 读取
│   ├── routes\
│   │   ├── auth.py
│   │   ├── llm_config.py
│   │   ├── profile.py
│   │   ├── generate.py
│   │   └── runs.py
│   ├── services\
│   │   ├── auth.py
│   │   ├── crypto.py
│   │   ├── quota.py
│   │   ├── resume.py          主档/定制简历 → Markdown 渲染、合并
│   │   └── llm\
│   │       ├── base.py
│   │       ├── factory.py
│   │       ├── gemini_provider.py
│   │       ├── openai_compat.py
│   │       └── service.py      generate_application() 封装 prompt 调用 + 解析
│   ├── db\
│   │   ├── models.py
│   │   ├── session.py
│   │   └── init.py            首启建表
│   └── prompts\
│       └── generate.txt
├── static\
│   ├── index.html
│   ├── app.js
│   └── style.css
├── api\
│   └── index.py               Vercel 入口，re-export app
├── tests\
│   ├── unit\
│   │   ├── test_resume_markdown.py
│   │   ├── test_llm_parser.py
│   │   └── test_quota.py
│   ├── integration\
│   │   ├── test_auth.py
│   │   ├── test_profile.py
│   │   └── test_generate.py
│   └── conftest.py            临时 DB + mock LLM provider fixture
├── data.db                    运行生成（git 忽略）
├── .env / .env.example
├── .gitignore
├── pyproject.toml
├── vercel.json
└── README.md
```

---

## 8. 测试策略

目标：`app/services` 覆盖率 80%+；routes 用集成测试覆盖。

| 层 | 测试对象 | 关键用例 |
|---|---|---|
| 单元 | `resume.py` markdown 渲染 | 各区块齐全/部分缺失/空主档；条目顺序；空数组不渲染空标题 |
| 单元 | `llm/base.py parse_llm_json` | 正常 JSON、带前后缀文字、缺括号、字段缺失 |
| 单元 | `quota.py` | 当日计数、跨日重置、超限判断 |
| 集成 | `/api/auth` | 注册成功 / 重复用户名 409 / 登录成功失败 / 受保护接口 401 |
| 集成 | `/api/profile` | 空主档 GET、PUT upsert、鉴权隔离（A 用户读不到 B） |
| 集成 | `/api/generate` | mock LLM：正常三部分 / 解析失败重试 / 主档空 PROFILE_EMPTY / 未配置 key / 配额耗尽 / 部分缺失 warning |
| 集成 | `/api/runs` | 列表倒序、单条读取、markdown 端点、鉴权隔离 |
| 手测 | 浏览器关键路径 | 注册→配 key 选模型→填主档→生成→查看三栏→导出 MD/打印 PDF |

工具：`pytest`、`httpx.AsyncClient`、临时 SQLite 隔离、LLM provider 依赖注入 mock。

---

## 9. 配置项（`.env.example`）

```
GEMINI_API_KEY=                 # 可选：系统级默认 key（用户未配时回退，可留空）
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=sqlite:///./data.db
DAILY_GENERATE_QUOTA=50
JWT_SECRET=<python -c "import secrets;print(secrets.token_urlsafe(64))">
BCRYPT_ROUNDS=12
LLM_ENC_KEY=<python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())">
```

---

## 设计澄清记录

| 维度 | 决策 |
|---|---|
| 形态 | 多用户 Web 应用，本地 + Vercel 部署 |
| 后端 | Python FastAPI（参照 recipe-recommender） |
| 数据库 | SQLite 本地 / Postgres 部署自动切换 |
| 前端 | 单页 Vue 3 CDN，零构建 |
| 用户系统 | 账号密码注册（开放）+ JWT |
| LLM | 每用户加密 key + provider(Gemini/OpenAI兼容) + 选模型 |
| 输入方式 | 结构化表单（分区块） |
| 简历定制 | 一份主档 + 按求职意向定制生成 |
| 生成调用 | 单次合并 LLM 调用返回三部分（简历/推荐/完善点） |
| 公司推荐 | 纯 LLM 生成（非真实招聘数据） |
| 导出 | 网页预览 + Markdown + 浏览器打印 PDF |
| 失败降级 | 静默 + warning，配额防呆 |
| 测试覆盖率 | services 80%+ |

---

## v2 设计：系统 UI 重设计 + 简历模板（2026-06-12）

### 目标
全面重做系统视觉，并内置 12 个简历模板（混合风格、可换主题色），覆盖网络流行的简历样式。

### 范围与约束
- **纯前端改造，零构建，不改后端、不动数据库**。模板与配色属表现层。
- 模板选择 + 主题色存 **localStorage**（全局偏好），不给 `resume_run` 加字段、不做 Neon 迁移。
- 现有后端测试不受影响；Markdown 导出端点不变（模板纯视觉）。
- 取舍：模板应用到「当前查看的任意简历」，不按每份历史记录单独存（后续可加 DB 字段再升级）。

### 系统 UI 重设计
- 设计系统：中性浅色背景、白卡+柔和阴影/圆角、统一间距刻度、可配置主色、中英文字体栈（PingFang/微软雅黑/系统无衬线；衬线模板用 Georgia/宋体）。
- 组件：导航 active 态、主/次/幽灵按钮、focus 环输入框、区块标题、空状态、加载态；**内联 toast 取代 `alert()`**。
- 逐页重做：登录、导航栏、主档表单、AI 设置、生成页（表单+三栏结果，窄屏堆叠）、历史卡片。

### 模板系统（12 个）
4 种结构布局 × 主题 CSS 组合；主题色用 CSS 变量，预设调色板（蓝/青/石板/紫/绿/玫红/琥珀/墨黑）可切换。

| # | 模板 | 结构 | 风格 | ATS |
|---|---|---|---|---|
| 1 | 经典 Classic | 单栏 | 衬线标题·白纸黑字·分隔线 | ✅ |
| 2 | 简约 Minimal | 单栏 | 大留白·细主色线 | ✅ |
| 3 | 现代 Modern | 单栏 | 主色区块标题+姓名 | ✅ |
| 4 | 商务 Professional | 单栏 | 顶部主色条·双色 | ✅ |
| 5 | 优雅 Elegant | 单栏 | 衬线(宋体)·精致 | ✅ |
| 6 | 紧凑 Compact | 单栏 | 小字密排·一页装更多 | ✅ |
| 7 | 科技 Tech | 单栏 | 等宽标题·开发者向 | ✅ |
| 8 | 时间轴 Timeline | 单栏+轴 | 竖线+节点 | ⚠️ |
| 9 | 双栏·左 Sidebar-L | 左侧栏 | 彩色侧栏放联系+技能 | ⚠️ |
| 10 | 双栏·右 Sidebar-R | 右侧栏 | 彩色侧栏在右 | ⚠️ |
| 11 | 创意 Creative | 左侧栏 | 大色块·彩色区块头 | ⚠️ |
| 12 | 卡片 Cards | 单栏 | 每区块为浅色卡片 | ⚠️ |

✅=ATS 友好（单栏规范）；⚠️=更好看但机器筛选解析略弱，界面标注提示。

### 模板选择 + 预览 + 导出
- 结果页新增模板选择条：横向缩略图 + 主题色圆点，点击即时套用。
- 简历预览为 A4 比例 `.resume-page`，套用当前模板/配色。
- PDF：`window.print()` 复用同一模板；打印样式表只显示 `.resume-page`、隐藏导航/表单/推荐/完善点，`print-color-adjust: exact` 保证彩色块/侧栏正常打印。
- Markdown：保持纯文本，端点不变。

### 文件结构（多小文件）
- `static/style.css`（系统 UI 重写）
- `static/templates.css`（12 模板布局+主题，新）
- `static/templates.js`（模板注册表 + `ResumePreview` 组件，新）
- `static/app.js`（接入模板选择、配色、toast、各页标记微调）

### 测试
前端零构建无 JS 测试框架：`node --check` 校验 `app.js`/`templates.js` 语法 + 启动冒烟（静态 200、页面可加载）+ 后端 45 测试仍全绿。视觉正确性由人工在浏览器逐模板 + 打印预览确认。

---

## 变更记录

- 2026-06-09 v1：初版设计
- 2026-06-12 v2：系统 UI 重设计 + 12 简历模板（纯前端、localStorage 持久化）
