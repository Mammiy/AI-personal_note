# Phase 1: 骨架、设计系统与账号

**Goal:** 让应用跑起来并锁定依赖；完成可复用的设计令牌与组件层；打通注册 / 登录 / 退出闭环。
**Prerequisites:** 无
**Deliverables:** 可启动的 Flask 应用、5 张数据表、`{code,message,data}` 统一响应、`api.js`、`base.css` 设计系统、主页与关于页、注册登录页

**Interface Decisions Implemented:** 设计令牌与字体分工、圆角/描边/阴影、按钮四态、卡片、表单与错误态、开关、Toast、空状态、加载态、顶栏登录态切换、羊皮纸底纹与主页背景图（签名元素）、内联 SVG 图标策略、主页与关于页布局与响应式。

---

## Task 1: 依赖锁定与应用骨架

**Goal:** 建立可重复安装、可启动的最小骨架，并把国内镜像写入安装说明。

**Files:**
- Create: `requirements.txt`、`requirements-dev.txt`、`config.py`、`extensions.py`、`app.py`、`README.md`
- Create: `routes/pages.py`、`routes/api_auth.py`、`routes/api_notes.py`、`routes/api_social.py`、`routes/api_misc.py`（各含一行 `bp = Blueprint("pages", __name__)` 等空壳，后续任务往里加路由）

**Steps:**

- [x] 写 `requirements.txt`，全部用 `==` 锁定：
  ```text
  Flask==3.1.3
  Werkzeug==3.1.9
  Flask-SQLAlchemy==3.1.1
  SQLAlchemy==2.0.54
  Flask-Login==0.6.3
  requests==2.32.5
  ```
- [x] 写 `requirements-dev.txt`：`pytest==8.4.2`
- [x] 写 `config.py`：
  ```python
  import os, secrets
  BASE_DIR = os.path.abspath(os.path.dirname(__file__))
  INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

  def _secret_key():
      key = os.environ.get("SECRET_KEY")
      if key:
          return key
      path = os.path.join(INSTANCE_DIR, "secret.key")
      if os.path.exists(path):
          return open(path, encoding="utf-8").read().strip()
      os.makedirs(INSTANCE_DIR, exist_ok=True)
      key = secrets.token_hex(32)
      with open(path, "w", encoding="utf-8") as f:
          f.write(key)
      return key

  class Config:
      SECRET_KEY = _secret_key()
      SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(INSTANCE_DIR, "notes.db")
      SQLALCHEMY_TRACK_MODIFICATIONS = False
      UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
      MAX_CONTENT_LENGTH = 5 * 1024 * 1024
      ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
      SESSION_COOKIE_HTTPONLY = True
      SESSION_COOKIE_SAMESITE = "Lax"
      AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.deepseek.com/v1")
      AI_API_KEY = os.environ.get("AI_API_KEY", "")
      AI_MODEL = os.environ.get("AI_MODEL", "deepseek-chat")
      AI_TIMEOUT = 20
      AI_MAX_CHARS = 5000
  ```
- [x] 写 `extensions.py`：`db = SQLAlchemy()`、`login_manager = LoginManager()`
- [x] 约定（后续所有阶段遵守）：笔记、评论、版本相关路由的 id 一律使用 `<int:id>` / `<int:vid>` 转换器，避免出现字符串 id 查询
- [x] 写 `app.py`：`create_app()` 中依次 `app.config.from_object(Config)`、`app.json.ensure_ascii = False`（保证中文不被转义）、`os.makedirs(UPLOAD_FOLDER, exist_ok=True)`、初始化 `db` 与 `login_manager`、`@login_manager.user_loader`、`@app.errorhandler(ApiError)`（转 `fail(e.code, e.message)`）、`@app.errorhandler(413)`（转 `fail(Code.UPLOAD_TOO_LARGE, "图片大小不能超过 5MB")`）、`@app.errorhandler(404)`（`request.path.startswith("/api/")` 时转 `fail(Code.NOT_FOUND, "内容不存在或已被删除")`，否则渲染 404 页面）、注册 5 个蓝图、`with app.app_context(): db.create_all()`；`__main__` 中 `app.run(host="127.0.0.1", port=5000, debug=True)`
- [x] 在 `routes/api_misc.py` 中加临时健康检查：`@bp.get("/api/health") -> ok({"status": "up"})`
- [x] 写 `README.md`：创建虚拟环境 → `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` → `pip install -r requirements-dev.txt -i 同镜像` → `python app.py` → 打开 `http://127.0.0.1:5000`；说明 `AI_API_KEY` 用环境变量注入。

**Verification:**
- [x] 运行：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
  - Expected: 结尾出现 `Successfully installed Flask-3.1.3 ... requests-2.32.5`
- [x] 运行：`python app.py`
  - Expected: 控制台出现 `Running on http://127.0.0.1:5000`，无 ImportError
- [x] 运行：`curl -i http://127.0.0.1:5000/api/health`
  - Expected: `HTTP/1.1 200 OK`，`Content-Type: application/json; charset=utf-8`，体为 `{"code":"OK","message":"操作成功","data":{"status":"up"}}`
- [x] 检查：`instance/notes.db` 与 `static/uploads/` 已生成

**Security/Boundary Notes:** `SECRET_KEY` 不写死在代码中，优先环境变量，缺省时落在 `instance/secret.key`（该文件不进仓库）。`MAX_CONTENT_LENGTH=5MB` 与 `SESSION_COOKIE_SAMESITE=Lax` 在此统一设置。

---

## Task 2: 数据模型与统一响应

**Goal:** 落地 5 张表与统一响应封装，使后续所有接口有一致的返回形状。

**Files:**
- Create: `models.py`、`utils/response.py`、`utils/errors.py`
- Test: `tests/conftest.py`、`tests/test_response.py`

**Steps:**

- [x] 写 `utils/response.py`：`class Code` 常量（`OK`、`PARAM_ERROR`、`UNAUTHORIZED`、`FORBIDDEN`、`NOT_FOUND`、`CONFLICT`、`SHARE_CLOSED`、`SHARE_PASSWORD_REQUIRED`、`SHARE_PASSWORD_WRONG`、`AI_NOT_CONFIGURED`、`AI_TIMEOUT`、`AI_ERROR`、`UPLOAD_TOO_LARGE`、`UPLOAD_TYPE_ERROR`、`SERVER_ERROR`）与 `ok(data=None, message="操作成功")`、`fail(code, message, http=200)`
- [x] 写 `utils/errors.py`：`class ApiError(Exception)` 含 `code`、`message`
- [x] 写 `models.py`：
  ```python
  class User(db.Model):
      id            = db.Column(db.Integer, primary_key=True)
      email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
      username      = db.Column(db.String(20), unique=True, nullable=False)
      password_hash = db.Column(db.String(200), nullable=False)
      created_at    = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

  class Note(db.Model):
      id                   = db.Column(db.Integer, primary_key=True)
      user_id              = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
      title                = db.Column(db.String(100), nullable=False)
      content              = db.Column(db.Text, nullable=False, default="")
      tags                 = db.Column(db.String(200), nullable=False, default="")   # 逗号分隔原文
      status               = db.Column(db.String(10), nullable=False, default="draft")  # draft|published
      is_shared            = db.Column(db.Boolean, nullable=False, default=False)
      share_token          = db.Column(db.String(32), unique=True, nullable=True, index=True)
      share_password_hash  = db.Column(db.String(200), nullable=True)
      allow_comments       = db.Column(db.Boolean, nullable=False, default=True)
      created_at           = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
      updated_at           = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
      published_at         = db.Column(db.DateTime, nullable=True)

  class NoteVersion(db.Model):
      id         = db.Column(db.Integer, primary_key=True)
      note_id    = db.Column(db.Integer, db.ForeignKey("note.id"), nullable=False, index=True)
      title      = db.Column(db.String(100), nullable=False)
      content    = db.Column(db.Text, nullable=False, default="")
      tags       = db.Column(db.String(200), nullable=False, default="")
      created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

  class Comment(db.Model):
      id          = db.Column(db.Integer, primary_key=True)
      note_id     = db.Column(db.Integer, db.ForeignKey("note.id"), nullable=False, index=True)
      user_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
      guest_name  = db.Column(db.String(20), nullable=True)
      content     = db.Column(db.Text, nullable=False)
      created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

  class Favorite(db.Model):
      id         = db.Column(db.Integer, primary_key=True)
      user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
      note_id    = db.Column(db.Integer, db.ForeignKey("note.id"), nullable=False)
      created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
      __table_args__ = (db.UniqueConstraint("user_id", "note_id", name="uq_user_note"),)
  ```
- [x] 写 `tests/conftest.py`：`create_app` 用 `SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"`，fixture `app`/`client`/`db_session`，每个用例前后 `db.create_all()` / `db.drop_all()`
- [x] 写 `tests/test_response.py`：断言 `ok()` 与 `fail()` 的 JSON 形状、HTTP 200、`message` 为中文；断言 `/api/health` 响应头含 `charset=utf-8`；断言未捕获异常与 `ApiError` 都转成 `{code,message,data}` 且 `message` 不含堆栈内容

**Verification:**
- [x] 运行：`python -m pytest tests/test_response.py -q`
  - Expected: `passed`，无 failed
- [x] 运行：`python -c "from app import create_app; from models import db; a=create_app(); import sqlite3; print([r[0] for r in sqlite3.connect('instance/notes.db').execute(\"select name from sqlite_master where type='table'\")])"`
  - Expected: 输出包含 `user`、`note`、`note_version`、`comment`、`favorite`

**Security/Boundary Notes:** 密码字段只存哈希，模型中不出现任何明文字段；`share_token` 唯一且可空，不允许用自增 id。

---

## Task 3: 前端请求层与设计系统

**Goal:** 建立唯一请求出口 `api.js`，并把需求文档的设计令牌、组件与签名元素落地为可复用样式。

**Files:**
- Create: `static/js/api.js`、`static/js/ui.js`、`static/css/base.css`、`static/css/pages.css`、`templates/base.html`、`templates/icons.html`
- Create: `static/img/home-bg.jpg`（复制自 `图片素材/个人笔记主页.jpg`）、`static/img/paper-bg.jpg`（复制自 `图片素材/个人笔记-笔记背景.jpg`）

**Steps:**

- [x] 写 `static/js/api.js`：
  ```js
  const Api = (() => {
    async function request(path, { method = "GET", body = null, form = null } = {}) {
      const opts = { method, credentials: "same-origin", headers: {} };
      if (form) opts.body = form;
      else if (body !== null) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
      const res = await fetch(path, opts);
      let data;
      try { data = await res.json(); }
      catch (e) { Toast.show("服务器繁忙，请稍后重试"); throw e; }
      if (data.code === "OK") return data.data;
      const msg = data.message || "服务器繁忙，请稍后重试";
      if (data.code === "UNAUTHORIZED") {
        Toast.show(msg);
        setTimeout(() => { location.href = "/login"; }, 800);
        throw new Error(msg);
      }
      Toast.show(msg);
      const err = new Error(msg); err.code = data.code; throw err;
    }
    return {
      get: p => request(p),
      post: (p, b) => request(p, { method: "POST", body: b }),
      put: (p, b) => request(p, { method: "PUT", body: b }),
      del: p => request(p, { method: "DELETE" }),
      upload: (p, form) => request(p, { method: "POST", form })
    };
  })();
  ```
- [x] 写 `static/js/ui.js`：`Toast.show(msg, type)`（成功/失败两态，2.5s 自动消失）、`UI.confirm(text)`（返回 Promise，用于删除二次确认）、`UI.copy(text)`（复制成功提示"已复制链接"）
- [x] 写 `static/css/base.css`，`:root` 中定义令牌：
  ```css
  :root{
    --ink:#3A3733; --ink-soft:#6B665E; --brown-strong:#6B4E2E; --brown:#8B7043;
    --gold:#C9A96A; --border:#E5DDCE; --success-ink:#3E7D4E; --success-bg:#E8F0E8;
    --danger:#C0392B; --surface:#FFFFFF; --surface-muted:#F5F2EC;
    --radius-sm:6px; --radius:8px; --radius-pill:999px;
    --shadow-card:0 2px 8px rgba(107,78,46,.08);
    --font-serif:"Noto Serif SC","Source Han Serif SC","SimSun",serif;
    --font-sans:system-ui,"PingFang SC","Microsoft YaHei",sans-serif;
  }
  ```
  并落地：`.app-bg`（羊皮纸底纹 `paper-bg.jpg`，`background-size:cover; background-attachment:fixed`）、`.container`（页宽 960–1100px 居中）、`.btn` 四态（默认/hover 加深一档/`:focus-visible` 2px `--gold` 外环/`:disabled` 40% 透明且 `pointer-events:none`）、`.btn--primary`（实底 `--brown` 白字）、`.btn--outline`、` .btn--text`、`.btn--danger`、`.card`（白底 + 1px `--border` + 8px 圆角 + `--shadow-card`）、`.field` 与 `.field--error`（`--danger` 描边 + 下方中文错误文案）、`.switch`（胶囊 + 滑块，激活 `--brown`）、`.chip` 与 `.chip--success`、`.modal-mask`（`rgba(58,55,51,.45)`）与 `.modal`、`.toast`、`.empty`、`.spinner`
  字体：页面标题/卡片标题/笔记标题/统计数字用 `--font-serif`，正文与控件用 `--font-sans`；圆角 6px（按钮输入）/8px（卡片）/999px（标签开关）；`@media (prefers-reduced-motion: reduce)` 关闭全部 transition/animation
- [x] 写 `templates/icons.html`：Jinja 宏 `icon(name)`，内联 SVG 覆盖 logo（笔记本 + 心）、pen、trash、eye、link、image、lock、share、copy、heart、quote、code、list-ul、list-ol、h1、h2、bold、italic，以及主页四项特性的圆环图标（quill / cloud / shield / bookmark）。全部描边风，不使用图标字体
- [x] 写 `templates/base.html`：`<header>`（logo + 品牌名 + 右侧导航，按 `current_user.is_authenticated` 渲染未登录 `登录/注册/关于` 或已登录 `我的文章/个人主页/关于/退出`）、`<main>` 插槽、`<footer>`（"用心记录，让知识更有价值。© 个人笔记"）、引入 `base.css`、`pages.css`、`vendor`、`api.js`、`ui.js`；页面唯一 `<h1>`；所有交互元素用 `<button>`/`<a>`，`<label for>` 关联
- [x] 复制素材：`cp "图片素材/个人笔记主页.jpg" static/img/home-bg.jpg`、`cp "图片素材/个人笔记-笔记背景.jpg" static/img/paper-bg.jpg`

**Verification:**
- [ ] 浏览器打开 `http://127.0.0.1:5000/api/health`，DevTools Console 执行 `fetch('/api/health').then(r=>r.json()).then(console.log)`
  - Expected: 打印 `{"code":"OK","message":"操作成功","data":{"status":"up"}}`；Network 面板显示响应头 `charset=utf-8`
- [ ] 交互冒烟：Console 执行 `Toast.show('测试提示')`
  - Expected: 出现顶部提示，2.5s 后自动消失；失败态为红色、成功态为绿色
- [ ] 样式冒烟：临时给 `/` 挂一个含全部组件的调试片段（按钮四态、卡片、开关、标签、弹窗、空状态、加载态）
  - Expected: 令牌生效（按钮底色 `rgb(139,112,67)`、焦点环 `#C9A96A`、卡片阴影存在），`prefers-reduced-motion` 开启后过渡消失

**Visual Verification:** 1440 / 768 / 375 三档视口检查顶栏不换行、卡片不溢出、羊皮纸底纹铺满且不重复错位；键盘 Tab 遍历按钮可见 2px 焦点环。

**Security/Boundary Notes:** `api.js` 是唯一请求出口，页面脚本不得直接 `fetch`；写操作强制 `application/json`（服务端侧在 Task 5 生效），配合 `SameSite=Lax` 阻断跨站提交。

---

## Task 4: 主页与关于页面

**Goal:** 落地需求文档 F3 与 F12，覆盖未登录/已登录两态。

**Files:**
- Create: `templates/index.html`、`templates/about.html`、`static/css/pages.css`（主页与关于区块）
- Modify: `routes/pages.py`

**Steps:**

- [x] `routes/pages.py` 增加 `GET / -> render_template("index.html")` 与 `GET /about -> render_template("about.html")`
- [x] `templates/index.html`：`.home-hero` 使用 `home-bg.jpg` 满屏铺底（`background-size:cover; background-position:center`）；左下文案区含 `h1`「记录生活 · 书写成长 / 遇见美好」（56–64px，字距加宽，`--gold` 装饰下划线）、简介段落（15px，行高 1.9）、主按钮「开始记录」→ `/register`（已登录时改为「进入工作台」→ `/workspace`）、次按钮「了解更多」→ `/about`；底部四项特性（简洁易用 / 云端同步 / 隐私保护 / 灵活分类），每项圆环描边图标 + 标题 + 一句说明
- [x] `templates/about.html`：项目简介、功能概览、技术栈说明、使用提示（如何分享 / 如何开启评论 / 如何使用 AI 润色）；`h1` 为「关于个人笔记」
- [x] `pages.css`：主页 Hero 文案定位与移动端 stacking（≤767px 文案居中、纵向堆叠）；关于页单栏卡片

**Verification:**
- [x] 访问 `/` 与 `/about`
  - Expected: 两页均返回 200，导航显示未登录态；点击「了解更多」进入 `/about`
- [x] 登录后访问 `/`
  - Expected: 顶栏切换为 `我的文章/个人主页/关于/退出`，「开始记录」变为「进入工作台」

**Visual Verification:** 1440 / 768 / 375 三档截图，核对 Hero 文案不被背景图压低对比度、四项特性在一行（桌面）与两行（≤767px）、无横向滚动条。

---

## Task 5: 注册、登录、退出

**Goal:** 落地需求文档 F1、F2 与 R1，建立账号闭环与权限基线。

**Files:**
- Create: `services/auth.py`、`templates/login.html`、`templates/register.html`、`static/js/login.js`、`static/js/register.js`
- Modify: `routes/api_auth.py`
- Test: `tests/test_auth.py`

**Steps:**

- [x] 写 `services/auth.py`：
  - `validate_register(email, username, password, confirm)`：邮箱格式（正则 `^[^@\s]+@[^@\s]+\.[^@\s]+$`）、用户名 2–20 字符、密码 ≥ 6 位、两次一致；任一不满足抛 `ApiError(PARAM_ERROR, 对应中文文案)`
  - `register(...)`：邮箱已存在抛 `ApiError(CONFLICT, "该邮箱已被注册")`，用户名已存在抛 `ApiError(CONFLICT, "该用户名已被使用")`；成功写入 `generate_password_hash` 并登录
  - `login(email, password)`：失败统一抛 `ApiError(PARAM_ERROR, "邮箱或密码错误")`，不区分账号不存在与密码错误
- [x] `routes/api_auth.py`：
  - `POST /api/auth/register`：`request.get_json(silent=True)` 为空或非 dict → `fail(PARAM_ERROR, "请填写邮箱")`；其余由 service 校验
  - `POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me`
  - 所有写接口：若 `request.content_type` 不含 `application/json` → 直接 `fail(PARAM_ERROR, "请求格式不正确")`
  - `login_manager.unauthorized_handler`：API 路径返回 `fail(UNAUTHORIZED, "请先登录")`，页面路径重定向 `/login`
- [x] `templates/register.html`：邮箱、用户名、密码、确认密码四个字段，`<label for>` 关联，错误文案容器带 `aria-describedby`
- [x] `templates/login.html`：邮箱、密码；提交失败显示"邮箱或密码错误"
- [x] `static/js/register.js` / `login.js`：提交时调 `Api.post`，成功后 `location.href = "/workspace"`；失败由 `api.js` 的 Toast 提示，已填内容保留
- [x] `routes/pages.py` 增加 `GET /login`、`GET /register`；已登录访问时 `redirect("/workspace")`
- [x] 写 `tests/test_auth.py`：注册成功返回 `OK` 且库中 `password_hash != 明文`；重复邮箱返回 `CONFLICT`「该邮箱已被注册」；重复用户名返回 `CONFLICT`「该用户名已被使用」；密码不一致/过短返回 `PARAM_ERROR`；登录错误密码返回「邮箱或密码错误」；未登录调受保护接口返回 `UNAUTHORIZED` 且 `data` 为 `null`

**Verification:**
- [x] 运行：`python -m pytest tests/test_auth.py -q`
  - Expected: 全部 `passed`
- [x] 手动：注册新账号 → 自动进入工作台（工作台页面此时可为占位）→ 退出 → 用错误密码登录
  - Expected: 依次看到「该邮箱已被注册」（重复时）、「邮箱或密码错误」；退出后顶栏回到未登录态
- [x] 运行：`curl -X POST http://127.0.0.1:5000/api/auth/login -d "email=a@b.com&password=x" -H "Content-Type: application/x-www-form-urlencoded"`
  - Expected: 返回 `{"code":"PARAM_ERROR","message":"请求格式不正确",...}`

**Security/Boundary Notes:** 密码只以 Werkzeug 哈希落库；登录失败信息不泄露账号是否存在；会话 Cookie `HttpOnly` + `SameSite=Lax`；写接口强制 JSON 以阻断跨站表单提交。

---

## Phase Completion Checklist

- [x] 5 个任务全部完成
- [x] `python -m pytest tests -q` 通过
- [x] `python app.py` 可启动，`/`、`/about`、`/login`、`/register` 均 200
- [x] 设计令牌与组件层可被后续页面直接复用（按钮/卡片/表单/开关/Toast/弹窗/空状态/加载态均已存在）
- [x] 注册 → 登录 → 退出闭环可用，未登录访问受保护接口返回 `UNAUTHORIZED`
- [x] 可进入 Phase 2
