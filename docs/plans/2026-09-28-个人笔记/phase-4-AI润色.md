# Phase 4: AI 润色

**Goal:** 落地需求文档 F11：后端润色服务（真实模型 + 本地模拟回退）、润色接口、划词右键菜单与左右对照弹窗、选区精确替换。
**Prerequisites:** Phase 2 完成（写/编辑页的 `<textarea>` 与工具栏选区操作）
**Deliverables:** `services/ai.py`、`POST /api/ai/polish`、右键上下文菜单、AI 润色弹窗、确认替换回写

**Interface Decisions Implemented:** AI 弹窗布局（标题「AI 文本润色」+ 左「原文」只读 / 右「润色结果」+ 右下「取消」「确认替换」）、四种弹窗状态（加载中 / 成功 / 失败+重试 / 无选区时菜单项置灰）、遮罩 `rgba(58,55,51,.45)`、宽度约 1000px、≤767px 左右栏纵向堆叠、键盘 Esc 关闭与焦点回归、加载中按钮禁用。

---

## Task 1: 后端润色服务与模拟回退

**Goal:** 实现提示词构造、OpenAI 兼容调用、超时与错误映射、本地确定性模拟，并加长度与频率限制。

**Files:**
- Create: `services/ai.py`
- Test: `tests/test_ai.py`

**Steps:**

- [x] 写 `services/ai.py`（顶部需 `import time`、`import requests`、`from flask import current_app`、`from flask_login import current_user`），核心内容：
  ```python
  SYSTEM_PROMPT = (
      "你是一位中文写作润色助手。请对用户输入文本进行润色：提升流畅度、清晰度与表达质量；"
      "不改变原意，不添加原文没有的事实；保持原文语言不变；"
      "完整保留 Markdown 标记（标题、列表、引用、代码块、链接、图片）与段落结构；"
      "只输出润色后的文本本身，不要输出任何解释、标题、前后缀或代码块围栏。"
  )

  def polish(text):
      cfg = current_app.config
      if not text or not text.strip():
          raise ApiError(Code.PARAM_ERROR, "请先选中要润色的文本")
      if len(text) > cfg["AI_MAX_CHARS"]:
          raise ApiError(Code.PARAM_ERROR, "选中内容过长，请分段润色")
      _check_rate(current_user.id)
      if not cfg["AI_API_KEY"]:
          return _simulate(text), True
      ...
      return _strip_fence(content), False
  ```
  - 调用：`POST {AI_BASE_URL}/chat/completions`，`Authorization: Bearer <key>`，body `{model, messages:[system,user], temperature:0.3, max_tokens:8192}`，`timeout=AI_TIMEOUT`
  - 异常映射：`requests.Timeout` → `AI_TIMEOUT`「润色请求超时，请稍后重试」；`requests.RequestException` → `AI_ERROR`「润色失败，请稍后重试」；`status_code != 200` → `AI_ERROR`「润色失败，请稍后重试」；解析失败 → `AI_ERROR`「润色失败，请稍后重试」；`content` 为空 → `AI_ERROR`「未能生成润色结果，请调整选中内容后重试」
  - `_strip_fence(s)`：去掉模型偶尔返回的首尾 ```` ``` ```` 围栏与首尾空行
  - `_simulate(text)`：确定性规则改写——
    - 逐行处理，`in_code` 标志在遇到以 ` ``` ` 开头的行时翻转；行首以 `#`、`>`、`-`、`*`、`|`、数字 + `.` 开头或处于代码块内时，只做空白规范化，不做词替换
    - 词替换表（单趟最长优先匹配，避免替换结果被同趟规则二次改写）：以 `services/ai.py` 的 `WORD_MAP` 为准（37 对常见等价词，如 `然后→随后`、`但是→然而`、`因为→由于`、`所以→因此`、`我觉得→我认为`、`其实→事实上`、`非常→极为`、`不错→很好`、`就像→犹如`、`使人→让人`、`提高→提升` 等）。**交付后修复记录**：初版只列 10 对词，普通文章几乎不产生改写，导致「确认替换」后正文一字不变（用户报障）；现已扩表并补标点与冗余规范化
    - 冗余表达精简：`的的→的`、`了了→了`、`有着→有`、`的话，→，`
    - 标点规范化：中文语境（前一字符为汉字）的半角 `, . ; : ? !` 转全角、重复标点合并、省略号统一为 `……`
    - 空白规范化：合并行内连续空格、去除行尾空格、去除中文标点前后的多余空格
    - 不使用随机数，保证同一输入结果一致
  - `_check_rate(user_id)`：模块级字典记录每个用户最近 60 秒的请求时间戳，超过 10 次抛 `ApiError(AI_ERROR, "润色请求过于频繁，请稍后再试")`
- [x] 写 `tests/test_ai.py`（用 `monkeypatch` 替换 `services.ai.requests.post`，不访问真实网络）：
  - 空文本 / 纯空白 → `PARAM_ERROR`「请先选中要润色的文本」
  - 长度 `AI_MAX_CHARS + 1` → `PARAM_ERROR`「选中内容过长，请分段润色」
  - `AI_API_KEY` 为空 → 返回 `(text, True)`，`text` 非空且与输入不同
  - 模拟对 `# 标题` 行与代码块内的行不做词替换
  - `requests.post` 抛 `requests.Timeout` → `AI_TIMEOUT`
  - 返回 `status_code=500` → `AI_ERROR`
  - 返回 `choices[0].message.content` 为空串 → `AI_ERROR`「未能生成润色结果，请调整选中内容后重试」
  - 返回内容被 ```` ``` ```` 包裹 → 结果中不含围栏
  - 正常返回 → `(content, False)`，且 `content` 与模型返回一致
  - 连续 11 次调用 → 第 11 次抛 `AI_ERROR`「润色请求过于频繁，请稍后再试」

**Verification:**
- [x] 运行：`python -m pytest tests/test_ai.py -q`
  - Expected: 全部 `passed`，且用例全程不发起真实网络请求（可用 `monkeypatch` 断言 `requests.post` 被调用次数）
- [x] 手动（不配置 `AI_API_KEY`）：在 Flask shell 中执行 `from services.ai import polish; print(polish("然后我觉得这个非常好")[0])`
  - Expected: 输出经过词替换的中文文本，无异常

**Security/Boundary Notes:** 密钥只在服务端读取，永不写入响应与日志；`message` 不含异常堆栈；输入长度与频率双重限制防滥用；`_simulate` 不依赖网络，保证密钥缺失时功能仍完整。

---

## Task 2: 润色接口

**Goal:** 暴露 `POST /api/ai/polish`，返回结构固定且可区分真实与模拟结果。

**Files:**
- Modify: `routes/api_misc.py`

**Steps:**

- [x] `routes/api_misc.py` 增加 `POST /api/ai/polish`（`@login_required`）：
  - body `{text}`；非 JSON 请求 → `fail(PARAM_ERROR, "请求格式不正确")`
  - 调 `services.ai.polish(text)`，成功返回 `ok({"text": ..., "simulated": bool})`
  - `ApiError` 由 `app.py` 的统一 errorhandler 转成 `fail(e.code, e.message)`
- [x] 在 `app.py` 的 errorhandler 中确认：未知异常 → `fail(SERVER_ERROR, "服务器繁忙，请稍后重试")`，且 `message` 不含堆栈（Task 1 已隐含，此处复核）

**Verification:**
- [x] 运行（已登录 Cookie）：`curl -X POST http://127.0.0.1:5000/api/ai/polish -H "Content-Type: application/json" -d '{"text":"然后我觉得这个非常好"}'`
  - Expected: `{"code":"OK","message":"操作成功","data":{"text":"<润色后文本>","simulated":true}}`
- [x] 运行：同上但 `text` 为 5001 字
  - Expected: `{"code":"PARAM_ERROR","message":"选中内容过长，请分段润色","data":null}`
- [x] 运行：未登录直接调用
  - Expected: `{"code":"UNAUTHORIZED","message":"请先登录","data":null}`

**Security/Boundary Notes:** 接口需登录，避免被当作开放文本接口；响应不含密钥与上游错误详情。

---

## Task 3: 右键上下文菜单与润色弹窗

**Goal:** 落地需求文档 F11 的交互界面：划词 → 右键菜单 → 弹窗加载 / 成功 / 失败四态。

**Files:**
- Create: `static/js/ai_polish.js`、`templates/note_edit.html`（追加菜单与弹窗结构）
- Modify: `static/js/note_edit.js`、`static/css/base.css`（弹窗与菜单样式）

**Steps:**

- [x] `templates/note_edit.html` 追加：
  - `<div id="ctx-menu" class="ctx-menu" hidden role="menu">`，内含单个 `<button role="menuitem" id="ctx-ai-polish">AI 润色</button>`
  - 弹窗结构：`.modal-mask` → `.modal`（宽约 1000px）→ 头部「AI 文本润色」（羽毛笔图标）+ 右上 `×` 关闭按钮 → 主体两栏（左栏标题「原文」+ `readonly` textarea；右栏标题「润色结果」+ `readonly` textarea，右栏标题右侧预留「模拟结果」徽标位）→ 底部右侧「取消」（outline）与「确认替换」（primary）
- [x] `static/css/base.css` 追加：`.ctx-menu`（白底 + 1px `--border` + 弱阴影 + 8px 圆角，禁用项 40% 透明）、`.modal-mask`（`rgba(58,55,51,.45)` 全屏 flex 居中）、`.modal`（`--surface` 底、8px 圆角、`--shadow-card`）、`.modal__body`（两栏等宽，中间 1px `--border` 分隔）、`.modal__footer`（右对齐）、`.spinner`（旋转指示；`prefers-reduced-motion` 下改为静态文字）、`.badge`（「模拟结果」小徽标，`--surface-muted` 底）
- [x] `static/js/ai_polish.js` 导出 `AiPolish.open({textarea, start, end, text})`：
  - 打开弹窗时保存 `start/end`（防止失焦丢失），左栏填入 `text`，右栏进入加载态（spinner + 「润色中…」），「确认替换」禁用
  - 调 `Api.post('/api/ai/polish', {text})`：成功把 `data.text` 填入右栏并启用「确认替换」；`data.simulated` 为真时显示「模拟结果」徽标
  - 失败：右栏显示后端 `message` + 「重试」按钮（重新发起同一请求）
  - 关闭：右上角 `×`、`Esc`、点击遮罩、「取消」四种方式，均关闭弹窗并把焦点与选区还给 `textarea`，编辑内容不变
  - 焦点：打开时焦点进入弹窗首个可聚焦元素，`Tab` 在弹窗内循环，关闭后焦点回到 `textarea`
- [x] `static/js/note_edit.js`：
  - 监听 `textarea` 的 `contextmenu`：`preventDefault()`；`selectionStart === selectionEnd` 时菜单项 `disabled`（置灰不可点），否则可点；菜单定位到 `event.clientX/clientY`
  - 键盘唤起：监听 `keydown`，`Shift+F10` 或 `ContextMenu` 键时在 `textarea` 中心位置打开菜单，焦点移到菜单项；`Enter` 激活、`Esc` 关闭并把焦点还给 `textarea`
  - 菜单项点击：关闭菜单 → `AiPolish.open({textarea, start: selStart, end: selEnd, text: selected})`
  - 页面任意位置点击与滚动时关闭菜单

**Verification:**
- [ ] 手动：编辑区不选文本右键
  - Expected: 菜单出现但「AI 润色」置灰不可点
- [ ] 手动：划词后右键 → 点「AI 润色」
  - Expected: 弹窗打开，左栏为选中原文，右栏显示「润色中…」，「确认替换」禁用
- [ ] 手动（不配置 `AI_API_KEY`）：等待返回
  - Expected: 右栏出现文本并显示「模拟结果」徽标，「确认替换」可点
- [ ] 手动：把 `AI_BASE_URL` 改成不可达地址后重复流程
  - Expected: 右栏显示「润色失败，请稍后重试」与「重试」按钮，左栏原文保留
- [ ] 键盘：划词 → `Shift+F10` → `Enter` → `Esc`
  - Expected: 菜单用键盘可唤起与激活；`Esc` 关闭弹窗后焦点回到编辑区且选区仍在
- [ ] 手动：点击遮罩与右上角 `×`
  - Expected: 弹窗关闭，编辑内容未变

**Visual Verification:** 1440 / 768 两档截图——加载中、成功、失败三态 + 无选区置灰态；弹窗宽约 1000px，左右栏等宽、中缝为 1px `--border`；≤767px 时左右栏纵向堆叠且按钮不溢出。

**Security/Boundary Notes:** 弹窗只把选中的文本发往后端，不上传整篇笔记；失败与取消路径都不修改编辑区内容。

---

## Task 4: 确认替换与选区回写

**Goal:** 落地需求文档 F11 的替换语义：只替换原选区，其余内容不变。

**Files:**
- Modify: `static/js/ai_polish.js`

**Steps:**

- [x] `AiPolish` 中「确认替换」点击处理：
  ```js
  const el = state.textarea;
  const value = el.value;
  el.value = value.slice(0, state.start) + state.result + value.slice(state.end);
  const caret = state.start + state.result.length;
  el.focus();
  el.setSelectionRange(caret, caret);
  Toast.show("已替换选中的文本");
  close();
  ```
- [x] 「确认替换」在加载中与失败态下保持禁用；成功后才启用
- [x] 连续快速点击只回写一次（点击后立即禁用按钮）
- [x] 关闭弹窗（`Esc` / 遮罩 / `×` / 取消）时**不**执行任何回写
- [x] 替换后触发一次 `input` 事件，确保预览区与保存逻辑拿到最新内容

**Verification:**
- [ ] 手动：正文 `AAA[选中BBB]CCC` → 润色 → 确认替换
  - Expected: 结果为 `AAA<润色后>CCC`，`AAA` 与 `CCC` 一字未改；光标停在替换内容末尾；Toast 提示
- [ ] 手动：润色失败或点「取消」
  - Expected: 正文保持 `AAABBBCCC` 原样
- [ ] 手动：连续快速点击「确认替换」3 次
  - Expected: 内容只被替换一次，不出现重复拼接
- [ ] 手动：替换后点「预览」
  - Expected: 预览显示替换后的最新内容

**Visual Verification:** 1440 截图——替换后编辑区内容正确、Toast 位于顶部且 2.5s 后消失。

---

## Phase Completion Checklist

- [x] 4 个任务全部完成
- [x] `python -m pytest tests -q` 通过（含 `test_ai.py` 全部用例）
- [x] 不配置 `AI_API_KEY` 时，划词 → 右键 → 润色 → 替换 全流程可用且标注「模拟结果」
- [x] 配置了 `AI_API_KEY` 时走真实模型（如无法联网，至少验证超时与错误分支提示正确）
- [x] 失败与取消路径均不修改编辑区内容
- [x] 键盘可完成划词润色全流程，`Esc` 与焦点回归正常
- [ ] 1440 / 768 / 375 三档弹窗截图符合需求文档线框
- [x] 可进入 Phase 5

**本阶段验证状态（实现记录）**

- 自动化：`python -m pytest tests -q` → 177 passed（基线 150）；`node --test "tests/js/*.test.js"` → 79 passed（基线 51）。
- Task 1 / Task 2 的命令型验证已用 pytest + 临时实例冒烟等价执行：模拟结果、空文本、5001 字、非 JSON、未登录、密钥已配但上游不可达（`AI_TIMEOUT`「润色请求超时，请稍后重试」）、60 秒内第 11 次（`AI_ERROR`「润色请求过于频繁，请稍后再试」）全部符合预期；`services.ai` 全部用例 monkeypatch `requests.post`，不发真实请求。
- Task 3 / Task 4 的交互验证由 `tests/js/ai_polish.test.js`（28 例）用最小 DOM 替身覆盖：加载态按钮禁用、只发送选中文本、模拟徽标、失败重试、四种关闭路径不改正文、关闭后焦点与选区回归、Tab 循环、连点只回写一次、替换后触发 `input` 事件。真实浏览器下的定位、像素与 Toast 位置**留待 Phase 5 人工核对**。
- 已知偏差：① 未配置密钥时按计划返回 `code=OK + simulated=true`（需求文档错误表写的 `AI_NOT_CONFIGURED` 未启用，因错误码无法同时回传润色结果）；② 失败时右栏与 `api.js` 的 Toast 会各显示一次同一后端文案，待 Phase 5 决定是否加静默选项。

**交付后修复记录（master 报障驱动）**

- **「AI 润色后内容仍然不变」**：根因是模拟回退的规则覆盖过窄——词表仅 10 对，实测 6 段真实文本中 5 段的输出与输入一字不差，前端把相同文本写回，用户看到的就是"没变化"。
  - `services/ai.py`：词表扩到 37 对、改为单趟最长优先匹配；新增中文语境标点规范化与冗余表达精简；结构行/代码块仍只做空白规范化，链接与图片不受影响。
  - `static/js/ai_polish.js`：新增「结果与原文一致」分支——提示「润色结果与原文一致，未作修改」，不再派发无意义的 `input` 事件、不做重复写回。
  - 回归用例：`tests/test_ai.py` 新增 4 例（普通散文必须改写、标点规范化、单趟只替换一次、确定性），`tests/js/ai_polish.test.js` 新增 1 例（一致时提示）。
- 验证：`python -m pytest tests -q` → 253 passed；`node --test "tests/js/*.test.js"` → 83 passed。
- 新增文案「润色结果与原文一致，未作修改」已补入需求文档「文案规范」表。
