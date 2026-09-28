# Phase 3: 分享、评论、收藏与个人主页

**Goal:** 落地需求文档 F7、F8、F9、F10：分享开关与密码访问、评论（含访客昵称与删除权限）、收藏、个人主页的收藏列表与版本历史。
**Prerequisites:** Phase 2 完成（笔记详情、渲染、登录态）
**Deliverables:** `services/share.py`、`services/comment.py`、`services/favorite.py`、分享页、详情页分享与评论卡片、收藏切换、个人主页

**Interface Decisions Implemented:** 详情页分享设置可折叠卡片（开关 + 只读链接 + 复制 + 密码输入）、评论卡片头部带开关与评论数、访客评论来源标注、分享页密码门四种状态（分享关闭 / 待输密码 / 密码错误 / 正常阅读）、个人主页三区块（个人信息 / 我的收藏 / 笔记历史）。

---

## Task 1: 分享开关、令牌与密码

**Goal:** 落地需求文档 F7 的作者侧能力：开关、链接、密码设置与复制。

**Files:**
- Create: `services/share.py`
- Modify: `routes/api_social.py`、`templates/note_detail.html`、`static/js/note_detail.js`、`static/css/pages.css`
- Test: `tests/test_share.py`

**Steps:**

- [ ] 写 `services/share.py`：
  - `ensure_token(note)`：`note.share_token` 为空时生成 `secrets.token_hex(16)`（32 字符）并保存
  - `set_share(note, is_shared)`：`True` 时确保令牌存在并置 `is_shared=True`；`False` 时置 `is_shared=False`（保留令牌，重新开启时链接不变）
  - `set_password(note, password)`：空字符串 → `share_password_hash = None`（移除密码）；否则写入 `generate_password_hash(password)`
  - `share_url(note)`：返回 `/s/<token>` 的相对路径（详情页展示时拼 `request.host_url` 得到完整链接）
  - `resolve(token)`：按令牌查笔记；不存在或 `is_shared` 为假 → 抛 `ApiError(SHARE_CLOSED, "分享已关闭")`
  - `needs_password(note, session)`：`note.share_password_hash` 为空 → `False`；否则返回 token 是否不在 `session.get("share_passed", [])` 中
  - `mark_passed(session, token)`：把 token 追加进 `session["share_passed"]` 并置 `session.modified = True`
  - `verify_password(note, password)`：不匹配抛 `ApiError(SHARE_PASSWORD_WRONG, "密码错误，请重新输入")`
- [ ] `routes/api_social.py` 增加 `PUT /api/notes/<id>/share`（`@login_required`，归属校验）：body `{is_shared, password}`；`password` 缺省表示不改密码，显式空字符串表示移除；返回 `{is_shared, share_url, has_password}`
- [ ] `templates/note_detail.html` 卡片三「分享设置」：头部标题 + 右侧「收起」链接（可折叠）；行一「分享已开启 / 分享已关闭」+ 开关；行二只读分享链接输入框 + 「复制」按钮；行三锁图标 + 密码输入（placeholder「输入新密码（留空移除）」）+ 「保存密码」按钮
- [ ] `static/js/note_detail.js`：开关切换调接口（切换中禁用防重复提交）；复制用 `UI.copy`（提示「已复制链接」）；密码保存后提示成功
- [ ] 写 `tests/test_share.py`：开启分享生成 32 字符令牌且 `is_shared=True`；关闭分享后 `/api/share/<token>` 返回 `SHARE_CLOSED` 且 `data` 为 `null`（不含标题与正文）；设置密码后未验证访问返回 `SHARE_PASSWORD_REQUIRED` 且响应不含正文；密码正确后再次访问返回正文；密码错误返回 `SHARE_PASSWORD_WRONG`；密码留空保存后访问不再需要密码；非作者改他人分享设置返回 `FORBIDDEN`

**Verification:**
- [ ] 运行：`python -m pytest tests/test_share.py -q`
  - Expected: 全部 `passed`
- [ ] 手动：详情页开分享 → 链接出现 → 点复制 → Toast「已复制链接」→ 设置密码 → 保存 → 关闭分享
  - Expected: 每一步都有中文反馈；关闭后链接保留但页面显示「分享已关闭」状态

**Visual Verification:** 1440 / 768 两档截图——分享开启与关闭两态；开关激活色为 `--brown`(#8B7043)；只读链接输入框为 `--surface-muted` 底；折叠后只留头部。

**Security/Boundary Notes:** 令牌用 `secrets.token_hex(16)`，不使用自增 id；关闭分享后对外一律 `SHARE_CLOSED` 且不返回任何笔记内容；密码只存哈希，接口永不返回密码原文。

---

## Task 2: 分享页与密码门

**Goal:** 落地需求文档 F7 的访客侧：`/s/<token>` 的四种状态，且在验证通过前不泄露任何内容。

**Files:**
- Create: `templates/share.html`、`static/js/share.js`
- Modify: `routes/api_social.py`、`routes/pages.py`、`static/css/pages.css`

**Steps:**

- [ ] `routes/pages.py` 增加 `GET /s/<token>`：渲染 `share.html` 骨架（**不含**任何笔记内容），把 token 传入模板
- [ ] `routes/api_social.py` 增加：
  - `GET /api/share/<token>`：`resolve` → 需密码时 `fail(SHARE_PASSWORD_REQUIRED, "该笔记需要密码才能查看")`；否则返回 `{title, content, updated_at, allow_comments}`
  - `POST /api/share/<token>/verify`：body `{password}`；成功 `mark_passed` 后 `ok()`；失败 `fail(SHARE_PASSWORD_WRONG, "密码错误，请重新输入")`
  - 两个接口均不要求登录
- [ ] `templates/share.html`：四种状态容器——`分享已关闭`（`--ink-soft` 居中提示，无任何笔记信息）、密码输入态（提示「该笔记需要密码才能查看」+ 密码框 + 「查看」按钮 + 错误文案位）、阅读态（标题 + 元信息 + 正文容器）、评论容器（Task 3 填充）
- [ ] `static/js/share.js`：加载时 `Api.get('/api/share/<token>')`；按 `err.code` 分支渲染 `SHARE_CLOSED` / `SHARE_PASSWORD_REQUIRED`；验证成功后重新拉取并渲染 `renderMarkdown(content)`；密码错误时保留输入框内容并提示

**Verification:**
- [ ] 手动（未登录、另开隐私窗口）：访问已关闭分享的链接 → 页面只显示「分享已关闭」
  - Expected: 页面源码中不含笔记标题与正文
- [ ] 访问设了密码的分享链接 → 输入错误密码 → 输入正确密码
  - Expected: 首次只显示密码界面；错误时提示「密码错误，请重新输入」且输入框不清空；正确后进入阅读页
- [ ] 运行：`curl -s http://127.0.0.1:5000/api/share/<未验证的带密码token>`
  - Expected: `{"code":"SHARE_PASSWORD_REQUIRED","message":"该笔记需要密码才能查看","data":null}`，响应体中不含标题与正文

**Visual Verification:** 分享页 1440 / 375 两档截图——分享关闭、待输密码、密码错误、正常阅读四态；≤375px 时密码框与按钮纵向排列且不溢出。

**Security/Boundary Notes:** 验证状态存于服务端签名会话（`session["share_passed"]`），不放在 URL 或前端存储；验证通过前的任何响应都不包含笔记内容。

---

## Task 3: 评论（含访客昵称与删除权限）

**Goal:** 落地需求文档 F8：评论开关、登录用户与分享访客两种身份、删除权限。

**Files:**
- Create: `services/comment.py`
- Modify: `routes/api_social.py`、`templates/note_detail.html`、`templates/share.html`、`static/js/note_detail.js`、`static/js/share.js`、`static/css/pages.css`
- Test: `tests/test_comment.py`

**Steps:**

- [ ] 写 `services/comment.py`：
  - `list_comments(note, viewer)`：`note.allow_comments` 为假时 `items` 返回空数组；否则返回按时间正序的评论，每项含 `id`、`display_name`（登录用户取 `username`，访客取 `guest_name`）、`is_guest`、`content`、`created_at`、`can_delete`
  - `can_delete(comment, viewer, note)`：笔记作者 → `True`；登录用户且 `comment.user_id == viewer.id` → `True`；其余（含访客）→ `False`
  - `add_comment(note, content, user=None, guest_name=None)`：内容为空 → `ApiError(PARAM_ERROR, "请输入评论内容")`；访客昵称不在 1–20 字符 → `ApiError(PARAM_ERROR, "请填写 1 到 20 个字符的昵称")`；`allow_comments` 为假 → `ApiError(FORBIDDEN, "评论已关闭")`
  - `set_enabled(note, enabled)`、`delete_comment(comment, viewer, note)`
- [ ] `routes/api_social.py` 增加：
  - `GET /api/notes/<id>/comments` → `{items, enabled}`
  - `POST /api/notes/<id>/comments`（`@login_required`）→ `{content}`，用 `current_user.username` 作为展示名
  - `PUT /api/notes/<id>/comments/enabled`（`@login_required`，归属校验）→ `{enabled}`
  - `DELETE /api/comments/<id>`（`@login_required`）→ 权限由 service 判定
  - `GET /api/share/<token>/comments`、`POST /api/share/<token>/comments`（`{content, guest_name}`，不需登录）
- [ ] `templates/note_detail.html` 卡片四「评论 (n)」：头部右侧「评论已开启 / 评论已关闭」+ 开关；评论项 `display_name` + 时间 + 右侧 `删除`（垃圾桶，`--danger`，仅 `can_delete` 为真时渲染）；底部输入框（placeholder「写下你的评论...」）+ 「发布」按钮；关闭时显示「评论已关闭」，空列表显示「还没有评论，来说点什么吧」
- [ ] `templates/share.html` 评论区：作者开启评论时显示昵称输入 + 内容输入 + 「发布」；关闭时显示「评论已关闭」
- [ ] `static/js/note_detail.js` / `share.js`：拉取列表、提交、删除走 `UI.confirm("确定删除这条评论吗？")`；开关切换调接口
- [ ] 写 `tests/test_comment.py`：登录用户评论展示用户名；访客带昵称评论 `is_guest=True` 且展示该昵称；昵称缺失返回 `PARAM_ERROR`；评论开关关闭后列表 `items` 为空且提交返回 `FORBIDDEN`「评论已关闭」；访客删除任意评论被拒；笔记作者可删他人评论；登录用户可删自己评论但不可删他人评论

**Verification:**
- [ ] 运行：`python -m pytest tests/test_comment.py -q`
  - Expected: 全部 `passed`
- [ ] 手动：作者侧发评论 → 关开关 → 详情页显示「评论已关闭」且历史评论不显示 → 再开开关恢复 → 分享页（隐私窗口）填昵称评论 → 作者删除该评论
  - Expected: 每一步符合；分享页访客看不到删除按钮
- [ ] 运行：`python -m pytest tests -q`
  - Expected: 全部 `passed`

**Visual Verification:** 1440 / 768 两档截图——评论开启（有评论 / 无评论）与关闭三态；访客来源标注清晰；删除按钮仅对有权限者出现。

**Security/Boundary Notes:** 访客无任何删除权限；评论内容按纯文本处理（不渲染 Markdown）；删除权限在 service 层统一判定，接口层不重复实现。

---

## Task 4: 收藏

**Goal:** 落地需求文档 F9：详情页收藏切换与个人主页收藏列表。

**Files:**
- Create: `services/favorite.py`
- Modify: `routes/api_social.py`、`routes/api_notes.py`、`templates/note_detail.html`、`static/js/note_detail.js`
- Test: `tests/test_comment.py` 之外新增 `tests/test_favorite.py`（在 `tests/` 下追加文件）

**Steps:**

- [ ] 写 `services/favorite.py`：
  - `toggle(user, note, on)`：`on=True` 时不存在则创建（重复调用幂等）；`on=False` 时存在则删除
  - `list_favorites(user)`：按 `Favorite.created_at` 倒序，返回 `{note_id, title, status, updated_at, favorited_at}`
  - `is_favorited(user, note)`：布尔
- [ ] `routes/api_social.py` 增加 `POST /api/notes/<id>/favorite`、`DELETE /api/notes/<id>/favorite`、`GET /api/favorites`（均 `@login_required`）
- [ ] `routes/api_notes.py` 的 `GET /api/notes/<id>` 返回中增加 `is_favorited`
- [ ] `templates/note_detail.html` 标题行增加收藏按钮（未收藏为描边心形，已收藏为实底心形），带 `aria-pressed`
- [ ] `static/js/note_detail.js`：点击切换并 Toast 反馈（「已收藏」/「已取消收藏」），即时更新图标
- [ ] 写 `tests/test_favorite.py`：收藏后 `GET /api/favorites` 命中；重复收藏只产生 1 条；取消后从列表消失；允许收藏自己的笔记；收藏列表按收藏时间倒序

**Verification:**
- [ ] 运行：`python -m pytest tests -q`
  - Expected: 全部 `passed`
- [ ] 手动：详情页点收藏 → 图标变实底 + Toast「已收藏」→ 再点取消 → 个人主页收藏列表同步变化
  - Expected: 状态即时反馈；重复点击不报错

**Visual Verification:** 1440 截图——未收藏与已收藏两态图标对比清晰，按钮可点区域 ≥ 32×32px。

---

## Task 5: 个人主页（信息、收藏、笔记历史）

**Goal:** 落地需求文档 F10：个人信息只读展示、收藏列表、笔记版本历史查看。

**Files:**
- Create: `templates/profile.html`、`static/js/profile.js`
- Modify: `routes/api_social.py`、`routes/api_notes.py`、`routes/pages.py`、`static/css/pages.css`
- Test: `tests/test_note.py` 追加版本接口用例

**Steps:**

- [ ] `routes/api_social.py` 增加 `GET /api/profile`（`@login_required`）→ `{user:{username, email, created_at}, favorites:[...], notes:[{id, title}]}`
- [ ] `routes/api_notes.py` 增加：
  - `GET /api/notes/<id>/versions`（归属校验）→ `{items:[{id, created_at, title}]}`，按时间倒序
  - `GET /api/notes/<id>/versions/<vid>`（归属校验）→ `{title, content, tags, created_at}`
- [ ] `templates/profile.html`：`h1`「个人主页」；区块一「个人信息」卡片（用户名、邮箱、注册时间，只读）；区块二「我的收藏」列表（点击进入详情，空态「还没有收藏的笔记」）；区块三「笔记历史」（笔记选择下拉 + 版本列表，点击查看旧版本）
- [ ] `static/js/profile.js`：拉取 profile 渲染三区块；选择笔记后拉版本列表；点击版本展示旧标题、标签与 `renderMarkdown(content)` 渲染的正文（只读，不提供恢复入口）；空态文案按需求文档
- [ ] `routes/pages.py` 增加 `GET /profile`（`@login_required`）
- [ ] `tests/test_note.py` 追加：两次更新产生 2 条版本记录且顺序为时间倒序；版本内容为对应历史快照；非作者访问他人版本接口返回 `FORBIDDEN`；新建笔记不产生版本记录

**Verification:**
- [ ] 运行：`python -m pytest tests -q`
  - Expected: 全部 `passed`
- [ ] 手动：编辑同一篇笔记两次 → 个人主页 → 选该笔记 → 版本列表出现 2 条 → 点最早一条查看旧内容
  - Expected: 旧版本正文与当时保存内容一致；页面无恢复按钮；无收藏/无版本时显示对应空态

**Visual Verification:** 1440 / 768 两档截图——有收藏、无收藏、版本历史三种状态；版本列表时间格式与详情页一致。

---

## Phase Completion Checklist

- [ ] 5 个任务全部完成
- [ ] `python -m pytest tests -q` 通过
- [ ] 分享开启/关闭/密码设置/密码验证四态可用，验证前不泄露内容
- [ ] 评论开关、登录用户与访客昵称、三种删除权限全部符合需求文档
- [ ] 收藏切换与列表正确，允许收藏自己的笔记
- [ ] 个人主页三区块可用，版本历史按时间倒序且只读
- [ ] 1440 / 768 / 375 三档截图无溢出
- [ ] 可进入 Phase 4
