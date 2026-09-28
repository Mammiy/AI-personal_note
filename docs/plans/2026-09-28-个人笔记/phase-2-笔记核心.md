# Phase 2: 笔记核心

**Goal:** 打通 Markdown 渲染与消毒、工作台、写/编辑（含版本快照）、列表搜索筛选、图片上传与详情页。
**Prerequisites:** Phase 1 完成（骨架、设计令牌、`api.js`、登录态）
**Deliverables:** `services/note.py`、`services/upload.py`、`markdown.js`、工作台页、写/编辑页、列表页、详情页、上传接口

**Interface Decisions Implemented:** 工作台三张统计卡与最近文章、写笔记工具栏方块按钮组与"预览"切换、详情页自上而下信息层级（标题与操作 → 元信息 → 正文 → 分享 → 评论）、状态标签与标签 chip、空状态文案、加载态。

---

## Task 1: Markdown 渲染与消毒

**Goal:** 建立预览与详情页共用的唯一渲染函数，并阻断 Markdown 中的 XSS。

**Files:**
- Create: `static/js/vendor/marked.umd.js`、`static/js/vendor/purify.min.js`、`static/js/markdown.js`
- Modify: `templates/base.html`（引入 vendor 与 `markdown.js`）

**Steps:**

- [x] 下载固定版本到 `static/js/vendor/`（`marked@18` 没有 `marked.min.js`，必须用 UMD 文件）：
  ```bash
  curl -L -o static/js/vendor/marked.umd.js https://cdn.jsdelivr.net/npm/marked@18.0.14/lib/marked.umd.js
  curl -L -o static/js/vendor/purify.min.js https://cdn.jsdelivr.net/npm/dompurify@3.4.16/dist/purify.min.js
  ```
- [x] 写 `static/js/markdown.js`：
  ```js
  window.renderMarkdown = function (md) {
    marked.setOptions({ gfm: true, breaks: true });
    const html = marked.parse(md || "");
    return DOMPurify.sanitize(html, { ADD_ATTR: ["alt", "title"] });
  };
  ```
- [x] 在 `templates/base.html` 末尾按顺序引入 `vendor/marked.umd.js`、`vendor/purify.min.js`、`markdown.js`

**Verification:**
- [ ] 浏览器控制台执行 `typeof marked` 与 `typeof DOMPurify`
  - Expected: 分别输出 `"object"` 与 `"object"`（都不是 `undefined`）
- [ ] 控制台执行 `renderMarkdown("# 标题\n**粗体**\n- 列表\n\n![](x.png)")`
  - Expected: 返回含 `<h1>`、`<strong>`、`<li>`、`<img>` 的 HTML 字符串
- [ ] XSS 用例：控制台执行 `renderMarkdown('<img src=x onerror="alert(1)">')` 与 `renderMarkdown('<script>alert(1)</script>')`
  - Expected: 输出中不含 `onerror`、`onload`、`javascript:`；不含 `<script>` 标签
- [ ] 引入一段真实笔记正文（含标题、引用、代码块、表格、图片）到预览区
  - Expected: 全部正常渲染，表格与代码块样式不溢出卡片

**Security/Boundary Notes:** 后端只存 Markdown 原文不做渲染；消毒只在前端一次完成，预览与详情页共用同一函数，避免两套渲染逻辑不一致。

---

## Task 2: 写笔记与编辑页（含版本快照）

**Goal:** 落地需求文档 F5 的写作能力：标题、标签、工具栏、预览、保存草稿、发布、版本快照。

**Files:**
- Create: `services/note.py`、`templates/note_edit.html`、`static/js/note_edit.js`
- Modify: `routes/api_notes.py`、`static/css/pages.css`
- Test: `tests/test_note.py`

**Steps:**

- [x] 写 `services/note.py`：
  - `normalize_tags(raw)`：按中英文逗号切分 → 去空白 → 去重 → 最多 5 个 → 每个截断至 12 字 → 返回 `list`；`to_tags_field(list)` 回写为英文逗号连接字符串
  - `validate(title, tags_raw)`：标题为空或 >100 字抛 `ApiError(PARAM_ERROR, "请填写标题")` / `"标题不能超过 100 字"`；正文不做必填限制
  - `create_note(user, data)`：写入并 `db.session.commit()`
  - `update_note(note, data)`：先写 `NoteVersion`（**更新前的** title/content/tags），再更新主体与 `updated_at`，两步在同一事务内提交；新建不产生版本记录
  - `publish_note(note, data)`：调用 `update_note`，`status="published"`，首次发布写 `published_at`，再次保存不覆盖原 `published_at`
  - `delete_note(note)`：级联删除该笔记的 `Comment`、`Favorite`、`NoteVersion` 后删主体
- [x] `routes/api_notes.py`：
  - `POST /api/notes`（body: `title`, `content`, `tags`, `status`）
  - `PUT /api/notes/<id>`（同上，`status` 为 `draft` 时存草稿、为 `published` 时发布）
  - 两者均 `@login_required`；非 JSON 请求 → `fail(PARAM_ERROR, "请求格式不正确")`；资源不存在或不属于当前用户 → `fail(FORBIDDEN, "没有权限执行该操作")`
  - 成功返回 `{note}`，含 `id`、`title`、`content`、`tags`（数组）、`status`、`created_at`、`updated_at`
- [x] `templates/note_edit.html`：
  - 顶部 `← 返回`、`保存草稿`（outline）、`发布文章`（primary，带纸飞机图标）
  - 卡片内：标题输入（placeholder「文章标题...」，28–30px 衬线）、标签行（label「标签：」+ 提示「用逗号分隔，例如：生活,工作,随笔」）
  - 工具栏方块按钮组（`--surface-muted` 底 + 描边）：H1、H2、B、I、引用、行内代码、无序列表、有序列表、链接、图片；右侧独立的「预览」按钮（眼睛图标）
  - `<textarea>`（placeholder「开始书写你的笔记...」）与 Markdown 语法提示；预览区容器
- [x] `static/js/note_edit.js`：
  - 工具栏用 `selectionStart/End` 实现：包裹类（加粗 `**`、斜体 `*`、行内代码 `` ` ``）包裹选区；行前缀类（`# `、`## `、`> `、`- `、`1. `）作用于每个选中行行首；链接插入 `[文字](url)` 并选中 `url` 占位
  - 图片按钮弹出小面板：「本地上传」触发 file input → `Api.upload('/api/upload', formData)` → 插入 `![](url)`；「图片链接」输入框 → 插入 `![说明](url)`
  - 预览切换：用 `renderMarkdown(textarea.value)` 渲染到预览区并隐藏 textarea，保持内容同步
  - 保存草稿 / 发布：调 `Api.post('/api/notes')` 或 `Api.put('/api/notes/<id>')`；草稿成功 Toast「草稿已保存」并停留；发布成功跳转 `/notes/<id>`
  - 页面需从 URL 读取 `id`（编辑态）并在加载时拉取笔记数据填充
- [x] `routes/pages.py` 增加 `GET /notes/new` 与 `GET /notes/<int:id>/edit`（均 `@login_required`）
- [x] 写 `tests/test_note.py`：新建草稿成功；更新已有笔记产生 1 条版本记录且版本内容为**更新前**内容；发布写入 `published_at` 且二次保存不覆盖；标题为空返回 `PARAM_ERROR`「请填写标题」；标签超过 5 个被截断为 5 个、单个超 12 字被截断；A 用户更新 B 用户笔记返回 `FORBIDDEN`；删除笔记后其评论、收藏、版本记录一并清空

**Verification:**
- [ ] 运行：`python -m pytest tests/test_note.py -q`
  - Expected: 全部 `passed`
- [ ] 手动：新建 → 输入标题/标签/正文 → 点「加粗」包裹选中词 → 点「预览」→ 返回编辑 → 保存草稿 → 再编辑 → 发布
  - Expected: 预览显示渲染结果且原文不丢；草稿保存后停留页面并提示「草稿已保存」；发布后跳转详情页；数据库 `note_version` 表新增 1 条记录

**Visual Verification:** 1440 / 768 / 375 三档截图——空编辑器、填写中、预览开启三种状态；≤767px 时工具栏换行且按钮不溢出；选中文本时工具栏按钮包裹正确。

**Security/Boundary Notes:** 所有笔记接口必须校验 `note.user_id == current_user.id`，禁止仅凭 id 操作；版本快照与主体更新同事务，失败回滚。

---

## Task 3: 工作台与我的文章列表

**Goal:** 落地需求文档 F4 与 F6：统计卡、最近文章、搜索与标签/状态筛选。

**Files:**
- Create: `templates/workspace.html`、`templates/notes.html`、`static/js/workspace.js`、`static/js/notes.js`
- Modify: `routes/api_notes.py`、`routes/api_misc.py`、`services/note.py`、`static/css/pages.css`
- Test: `tests/test_note.py`（追加列表用例）

**Steps:**

- [x] `services/note.py` 增加：
  - `workspace_summary(user)` → `{draft_count, published_count, favorite_count, recent: [最近 5 篇的 id/title/status/updated_at]}`
  - `list_notes(user, keyword=None, tag=None, status=None)` → 按 `updated_at` 倒序；`keyword` 同时匹配标题与正文（`LIKE %kw%`）；`tag` 精确匹配解析后的标签；`status` 为 `draft`/`published`，为空表示全部
  - `user_tags(user)` → 该用户全部笔记标签去重后的列表
- [x] `routes/api_misc.py` 增加 `GET /api/workspace/summary`（`@login_required`）
- [x] `routes/api_notes.py` 增加 `GET /api/notes`（参数 `keyword`、`tag`、`status`，返回 `{items, tags}`）
- [x] `templates/workspace.html`：`h1`「工作台」+ 右侧 `新建文章`（primary）与 `我的文章`（outline）；三张等宽统计卡（大号衬线数字 + 灰色小标签：草稿 / 已发布 / 收藏）；「最近文章」卡片，每行标题 + 状态标签 + 更新时间，点击进入详情；无数据时显示「还没有文章，点"新建文章"开始记录」
- [x] `static/js/workspace.js`：拉取 summary 渲染统计与最近文章；失败由 Toast 提示
- [x] `templates/notes.html`：搜索框、标签筛选（多选 chip）、状态筛选（全部 / 草稿 / 已发布）、「清空筛选」、列表区；空态区分「没有找到匹配的笔记，换个关键词试试」与「还没有任何笔记」
- [x] `static/js/notes.js`：输入即时过滤（前端对已加载列表过滤，不重复请求）；筛选条件数量显示与一键清空
- [x] `routes/pages.py` 增加 `GET /workspace` 与 `GET /notes`（均 `@login_required`）
- [x] `tests/test_note.py` 追加：关键词命中标题与正文各 1 例；标签筛选、状态筛选、三者叠加各 1 例；`user_tags` 去重正确；列表只返回当前用户笔记

**Verification:**
- [ ] 运行：`python -m pytest tests/test_note.py -q`
  - Expected: 全部 `passed`
- [ ] 手动：创建 3 篇（2 草稿 1 已发布，带不同标签）→ 工作台核对统计数字与最近文章顺序 → 列表页搜索关键词、切换标签与状态
  - Expected: 统计数字与数据库一致；最近文章按更新时间倒序；搜索/筛选结果正确，叠加条件生效，清空后恢复全部

**Visual Verification:** 工作台 1440 / 768 两档（有数据与零数据）；列表页 1440 / 768 / 375 三档（列表、搜索无结果、筛选命中、空态）。

---

## Task 4: 图片上传

**Goal:** 落地需求文档 F5 工具栏图片能力与 Security 中的上传约束。

**Files:**
- Create: `services/upload.py`
- Modify: `routes/api_misc.py`、`static/js/note_edit.js`（已在 Task 2 预留入口）

**Steps:**

- [x] 写 `services/upload.py`：`save_image(file)`：
  - 扩展名取 `filename.rsplit(".", 1)[-1].lower()`，不在 `ALLOWED_IMAGE_EXT` 内抛 `ApiError(UPLOAD_TYPE_ERROR, "仅支持 png、jpg、jpeg、webp、gif 格式的图片")`
  - 目标文件名 `uuid4().hex + "." + ext`（不使用原始文件名），保存到 `UPLOAD_FOLDER`
  - 返回 `/static/uploads/<filename>`
- [x] `routes/api_misc.py` 增加 `POST /api/upload`（`@login_required`，字段名 `file`）：无文件 → `fail(PARAM_ERROR, "请选择要上传的图片")`；写盘失败 → `fail(SERVER_ERROR, "图片上传失败，请稍后重试")`；成功返回 `{url}`
- [x] `app.py` 的 `413` handler 已在 Phase 1 注册，确认其对 `/api/upload` 返回 `{"code":"UPLOAD_TOO_LARGE","message":"图片大小不能超过 5MB"}`
- [x] `static/js/note_edit.js` 上传分支接入 `Api.upload`

**Verification:**
- [x] 运行：`curl -F "file=@static/img/paper-bg.jpg" http://127.0.0.1:5000/api/upload`（先登录并保存 Cookie）
  - Expected: `{"code":"OK","message":"操作成功","data":{"url":"/static/uploads/<32位十六进制>.jpg"}}`
- [x] 上传 `.txt` 改名为 `.jpg` 的伪图片之外的非法扩展名（如 `a.exe`）
  - Expected: `{"code":"UPLOAD_TYPE_ERROR","message":"仅支持 png、jpg、jpeg、webp、gif 格式的图片"}`
- [x] 上传 6MB 图片
  - Expected: `{"code":"UPLOAD_TOO_LARGE","message":"图片大小不能超过 5MB"}`
- [ ] 手动：编辑器点图片 → 上传 → 正文中出现 `![](url)` → 预览中图片正常显示

**Security/Boundary Notes:** 扩展名白名单 + 5MB 限制 + 随机文件名；不使用 `secure_filename` 后的原始名，避免覆盖与路径穿越；上传目录只用于静态读取。

---

## Task 5: 笔记详情页

**Goal:** 落地需求文档 F5 的详情页：渲染正文、元信息、编辑与删除入口；为 Phase 3 预留分享与评论卡片位置。

**Files:**
- Create: `templates/note_detail.html`、`static/js/note_detail.js`
- Modify: `routes/api_notes.py`、`routes/pages.py`、`static/css/pages.css`

**Steps:**

- [x] `routes/api_notes.py` 增加：
  - `GET /api/notes/<id>`：归属校验后返回 `{note, can_edit}`（`can_edit` 恒为 `true`，因为只有作者可访问）
  - `DELETE /api/notes/<id>`：调 `delete_note`，成功返回 `{}`
- [x] `routes/pages.py` 增加 `GET /notes/<int:id>`（`@login_required`，非作者返回 404 页面）
- [x] `templates/note_detail.html`：`← 返回列表`；卡片一为标题（`h1`，衬线 28–30px）与右上 `编辑`（铅笔图标）、`删除`（垃圾桶图标，`--danger`）；元信息行：状态标签（`已发布` 用 success 配色，`草稿` 用灰色）、标签 chip、`创建: YYYY/M/D HH:MM`、`更新: YYYY/M/D HH:MM`；卡片二为正文容器（由 `renderMarkdown` 填充）；预留卡片三（分享设置）与卡片四（评论）的容器
- [x] `static/js/note_detail.js`：拉取笔记 → 渲染标题、元信息、正文 → 绑定编辑跳转 `/notes/<id>/edit` → 删除走 `UI.confirm("确定删除这篇笔记吗？删除后无法恢复")`，确认后 `Api.del` 并跳 `/notes`
- [x] 删除确认弹窗复用 `ui.js` 的 `UI.confirm`

**Verification:**
- [ ] 手动：进入草稿详情 → 状态标签为灰色「草稿」；发布后为绿色「已发布」；点编辑进入编辑页；点删除弹出「确定删除这篇笔记吗？删除后无法恢复」，确认后跳列表且笔记消失
  - Expected: 全部符合；取消删除时笔记保留
- [x] 运行：`python -m pytest tests -q`
  - Expected: 全部 `passed`（含删除级联用例）

**Visual Verification:** 1440 / 768 两档截图——草稿态与已发布态各一张；正文中的标题、列表、代码块、引用、图片层级与间距与参考截图一致，长内容不溢出卡片。

---

## Phase Completion Checklist

- [x] 5 个任务全部完成
- [x] `python -m pytest tests -q` 通过（含 auth / note / response 用例）
- [x] 新建 → 草稿 → 编辑 → 发布 → 详情 → 删除 全流程可用
- [x] 搜索 / 标签 / 状态筛选结果正确；工作台统计与最近文章正确
- [ ] 图片上传成功并在正文渲染；非法类型与超限被拒
- [ ] Markdown XSS 用例在浏览器中不执行
- [ ] 1440 / 768 / 375 三档截图无横向滚动条、无溢出
- [x] 可进入 Phase 3

**本阶段验证状态（实现记录）**

- 自动化：`python -m pytest tests -q` → 82 passed；`node --test "tests/js/*.test.js"` → 39 passed。
- 上述Verification 步骤中标注「浏览器控制台 / 手动 / 截图」的条目本环境无浏览器可执行，**统一在 Phase 5（全量验收与视觉打磨）执行**；
  其中可用的替代证据：`renderMarkdown` 与 XSS 消毒链路已由 `tests/js/markdown.test.js` 用真实 marked + 断言必经 `DOMPurify.sanitize` 覆盖；
  上传成功/非法类型/超限三条已由 `tests/test_upload.py` 与临时实例冒烟覆盖。
