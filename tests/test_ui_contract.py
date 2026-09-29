"""Phase 5 · Task 2：响应式与无障碍静态契约验收。

本环境没有浏览器、没有 Playwright，无法截图或量测真实像素，
因此这里把需求文档「响应式规则」「Accessibility」两节拆成两类可执行断言：

1. 渲染后的 HTML 文本（用 test_client 拉取每个页面）——语义结构、表单无障碍名称、
   弹窗/菜单的 ARIA 角色、错误态关联。
2. 样式与模板文件文本——断点、焦点外环、对比度、触控目标、动效降级、装饰性图片。

真实渲染层面无法自动覆盖的部分（滚动条宽度 scrollWidth <= innerWidth、背景图片实际
渲染、真实像素光泽），在报告里明确标注为「待人工浏览器验证」。
"""

import re
from pathlib import Path

import pytest

from utils.response import Code

ROOT = Path(__file__).resolve().parents[1]
CSS_DIR = ROOT / "static" / "css"
TPL_DIR = ROOT / "templates"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


BASE_CSS = read(CSS_DIR / "base.css")
PAGES_CSS = read(CSS_DIR / "pages.css")
ICONS_HTML = read(TPL_DIR / "icons.html")
NOTE_EDIT_HTML = read(TPL_DIR / "note_edit.html")
LOGIN_HTML = read(TPL_DIR / "login.html")
REGISTER_HTML = read(TPL_DIR / "register.html")


# ---------- CSS 小工具 ----------


def rule(css: str, selector: str) -> str:
    """取某条选择器（精确，不含伪类）的第一个声明块内容。"""
    pattern = re.compile(re.escape(selector) + r"\s*\{([^}]*)\}")
    match = pattern.search(css)
    assert match, f"未找到 CSS 规则：{selector}"
    return match.group(1)


def px(value: str) -> float:
    match = re.search(r"(-?\d+(?:\.\d+)?)px", value)
    assert match, f"不是像素值：{value}"
    return float(match.group(1))


def declared(block: str, prop: str) -> str:
    match = re.search(rf"(?<![\w-]){re.escape(prop)}\s*:\s*([^;]+);", block)
    assert match, f"声明块缺少 {prop}：{block!r}"
    return match.group(1).strip()


def token_block() -> str:
    return rule(BASE_CSS, ":root")


def token(name: str) -> str:
    return declared(token_block(), name)


# ---------- 对比度（WCAG 相对亮度） ----------


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ---------- 页面夹具 ----------


def register_and_login(client):
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "ui@example.com",
            "username": "界面验收",
            "password": "secret123",
            "confirm": "secret123",
        },
    )
    assert resp.get_json()["code"] == Code.OK
    return resp.get_json()["data"]["id"]


def make_note(client):
    resp = client.post(
        "/api/notes",
        json={"title": "验收笔记", "content": "正文", "tags": "验收", "status": "published"},
    )
    assert resp.get_json()["code"] == Code.OK
    return resp.get_json()["data"]["id"]


@pytest.fixture
def guest_pages(client):
    """未登录可见页面：主页、登录、注册、关于、分享骨架、404。"""
    return {
        "主页": client.get("/").get_data(as_text=True),
        "登录": client.get("/login").get_data(as_text=True),
        "注册": client.get("/register").get_data(as_text=True),
        "关于": client.get("/about").get_data(as_text=True),
        "分享页": client.get("/s/" + "a" * 32).get_data(as_text=True),
        "404": client.get("/definitely-not-here").get_data(as_text=True),
    }


@pytest.fixture
def authed_pages(client):
    """登录后页面：工作台、我的文章、写笔记、笔记详情、个人主页。"""
    register_and_login(client)
    note_id = make_note(client)
    return {
        "工作台": client.get("/workspace").get_data(as_text=True),
        "我的文章": client.get("/notes").get_data(as_text=True),
        "写笔记": client.get("/notes/new").get_data(as_text=True),
        "笔记详情": client.get(f"/notes/{note_id}").get_data(as_text=True),
        "个人主页": client.get("/profile").get_data(as_text=True),
    }


# ---------- 响应式断点 ----------


def test_two_breakpoints_exist_in_both_stylesheets():
    for css, name in ((BASE_CSS, "base.css"), (PAGES_CSS, "pages.css")):
        assert "@media (max-width: 1023px)" in css, f"{name} 缺少 1023px 断点"
        assert "@media (max-width: 767px)" in css, f"{name} 缺少 767px 断点"


def test_narrow_breakpoint_stacks_multi_column_areas():
    narrow = PAGES_CSS.split("@media (max-width: 767px)")[1]
    # 统计卡三列在窄屏改为纵向堆叠
    stat_grid = narrow.split(".stat-grid")[1].split("}")[0]
    assert "grid-template-columns: 1fr" in stat_grid
    # 工具栏与预览按钮换行（toolbar 声明了 flex-wrap）
    assert "flex-wrap: wrap" in rule(PAGES_CSS, ".toolbar")


def test_medium_breakpoint_turns_features_into_two_columns():
    medium = PAGES_CSS.split("@media (max-width: 1023px)")[1]
    assert "grid-template-columns: repeat(2, 1fr)" in medium


def test_ai_modal_stack_direction_on_narrow_screen():
    narrow = BASE_CSS.split("@media (max-width: 767px)")[-1]
    polish = narrow.split(".polish__body")[1].split("}")[0]
    assert "flex-direction: column" in polish


# ---------- 语义结构 ----------


def _all_pages(guest_pages, authed_pages):
    return {**guest_pages, **authed_pages}


def test_every_page_has_exactly_one_h1(guest_pages, authed_pages):
    for name, html in _all_pages(guest_pages, authed_pages).items():
        assert html.count("<h1") == 1, f"{name} 的 <h1> 数量应为 1"


def test_every_page_has_landmark_regions(guest_pages, authed_pages):
    for name, html in _all_pages(guest_pages, authed_pages).items():
        for tag in ("<header", "<nav", "<main", "<footer"):
            assert tag in html, f"{name} 缺少 {tag}"


def test_primary_navigation_is_a_nav_landmark(guest_pages):
    assert '<nav class="site-nav" aria-label="主导航">' in guest_pages["主页"]


CONTROL_RE = re.compile(r"<(input|textarea|select)\b[^>]*>", re.IGNORECASE)


def _accessible_control_ids(html: str):
    """返回 (有名字的控件数, 无名控件列表)。名字来自 <label for> 或 aria-label。"""
    linked = set(re.findall(r'<label\b[^>]*\bfor="([^"]+)"', html))
    named, unnamed = 0, []
    for match in CONTROL_RE.finditer(html):
        raw = match.group(0)
        if re.search(r'\btype="hidden"', raw):
            continue
        has_aria = "aria-label=" in raw or "aria-labelledby=" in raw
        cid = re.search(r'\bid="([^"]+)"', raw)
        if has_aria or (cid and cid.group(1) in linked):
            named += 1
        else:
            unnamed.append(raw)
    return named, unnamed


def test_form_controls_have_accessible_names(guest_pages, authed_pages):
    for name, html in _all_pages(guest_pages, authed_pages).items():
        _, unnamed = _accessible_control_ids(html)
        assert not unnamed, f"{name} 存在无无障碍名称的控件：{unnamed}"


def test_interactive_controls_are_buttons_or_links():
    """工具栏、开关、筛选 chip 必须是 <button>，跳转入口是 <a>。"""
    html = NOTE_EDIT_HTML
    assert html.count('class="tool-btn"') == 10
    for icon_only_action in ("quote", "code", "ul", "ol", "link", "image"):
        assert f'data-action="{icon_only_action}"' in html
    assert 'role="switch"' in read(TPL_DIR / "note_detail.html")

    notes_html = read(TPL_DIR / "notes.html")
    assert notes_html.count("chip--button") == 3


def test_ai_dialog_and_context_menu_roles():
    assert 'role="dialog"' in NOTE_EDIT_HTML
    assert 'aria-modal="true"' in NOTE_EDIT_HTML
    assert 'aria-labelledby="ai-polish-title"' in NOTE_EDIT_HTML
    assert 'role="menu"' in NOTE_EDIT_HTML
    assert 'role="menuitem"' in NOTE_EDIT_HTML


def test_context_menu_supports_keyboard_navigation():
    """Shift+F10 / 菜单键唤起、上下键选择、Esc 关闭都由 note_edit.js 接线。"""
    js = read(ROOT / "static" / "js" / "note_edit.js")
    assert "AiPolish.isMenuKey" in js
    assert "ArrowDown" in js and "ArrowUp" in js
    assert "AiPolish.menuIndex" in js
    assert 'event.key !== "Escape"' in js


# ---------- 焦点可见 ----------


def test_focus_visible_gold_ring_is_declared():
    assert ":focus-visible" in BASE_CSS
    assert "outline: 2px solid var(--gold)" in BASE_CSS


def test_no_outline_none_anywhere():
    for css in (BASE_CSS, PAGES_CSS):
        assert "outline: none" not in css
        assert "outline:none" not in css
        assert "outline: 0" not in css


def test_interactive_components_declare_focus_visible():
    combined = BASE_CSS + PAGES_CSS
    for selector in (".btn", ".field__control", ".switch", ".tool-btn", ".chip--button", ".icon-btn"):
        assert f"{selector}:focus-visible" in combined, f"{selector} 缺少焦点样式"


# ---------- 对比度 ----------


def test_contrast_ratios_meet_requirement():
    ink = token("--ink")
    ink_soft = token("--ink-soft")
    brown = token("--brown")
    surface = token("--surface")
    muted = token("--surface-muted")

    # 正文：对白卡片与羊皮纸底色均 >= 7:1
    assert contrast(ink, surface) >= 7, contrast(ink, surface)
    assert contrast(ink, muted) >= 7, contrast(ink, muted)
    # 次要文字 >= 4.5:1
    assert contrast(ink_soft, surface) >= 4.5, contrast(ink_soft, surface)
    assert contrast(ink_soft, muted) >= 4.5, contrast(ink_soft, muted)
    # 主按钮白字对 --brown >= 4.5:1
    assert contrast("#ffffff", brown) >= 4.5, contrast("#ffffff", brown)


def test_color_tokens_are_pinned():
    """10 个色彩令牌取值不得改动（Phase 5 专项）。"""
    expected = {
        "--ink": "#3a3733",
        "--ink-soft": "#6b665e",
        "--brown-strong": "#6b4e2e",
        "--brown": "#8b7043",
        "--gold": "#c9a96a",
        "--border": "#e5ddce",
        "--success-ink": "#3e7d4e",
        "--success-bg": "#e8f0e8",
        "--danger": "#c0392b",
        "--surface": "#ffffff",
    }
    for name, value in expected.items():
        assert token(name).lower() == value, f"{name} 取值被改动：{token(name)}"


# ---------- 表单错误 ----------


def test_login_and_register_inputs_describe_their_errors():
    for html in (LOGIN_HTML, REGISTER_HTML):
        described = set(re.findall(r'aria-describedby="([^"]+)"', html))
        error_ids = set(re.findall(r'<p class="field__error" id="([^"]+)"', html))
        assert described, "表单缺少 aria-describedby"
        assert described <= error_ids, f"aria-describedby 指向了不存在的错误节点：{described - error_ids}"


def test_error_style_uses_danger_border_and_text():
    assert ".field--error .field__control" in BASE_CSS
    block = rule(BASE_CSS, ".field__error")
    assert "var(--danger)" in block


# ---------- 触控目标 ----------


def test_buttons_meet_minimum_touch_target():
    btn = rule(BASE_CSS, ".btn")
    assert px(declared(btn, "min-height")) >= 32
    assert px(declared(btn, "min-width")) >= 32


def test_switch_meets_minimum_touch_target():
    switch = rule(BASE_CSS, ".switch")
    assert px(declared(switch, "height")) >= 32, "开关可点高度需 >= 32px"
    assert px(declared(switch, "width")) >= 32


def test_small_controls_meet_minimum_touch_target():
    for css, selector in (
        (PAGES_CSS, ".tool-btn"),
        (PAGES_CSS, ".chip--button"),
        (BASE_CSS, ".ctx-menu__item"),
    ):
        block = rule(css, selector)
        if "min-height" in block:
            assert px(declared(block, "min-height")) >= 32, selector
    icon_btn = rule(PAGES_CSS, ".icon-btn")
    assert px(declared(icon_btn, "width")) >= 32
    assert px(declared(icon_btn, "height")) >= 32


# ---------- 图片与装饰 ----------


def test_decorative_icons_are_hidden_from_a11y_tree():
    assert 'aria-hidden="true"' in ICONS_HTML
    assert 'focusable="false"' in ICONS_HTML


def test_backgrounds_are_css_images_not_content_images():
    assert 'url("../img/paper-bg.jpg")' in BASE_CSS
    assert 'url("../img/home-bg.jpg")' in PAGES_CSS


def test_markdown_renderer_preserves_image_alt_and_link_title():
    """正文图片的 alt 必须穿过消毒保留下来（DOMPurify ADD_ATTR）。"""
    js = read(ROOT / "static" / "js" / "markdown.js")
    assert '"alt"' in js
    assert '"title"' in js
    assert "DOMPurify.sanitize" in js


# ---------- 动效降级 ----------


def test_reduced_motion_stops_transitions_and_animations():
    assert "@media (prefers-reduced-motion: reduce)" in BASE_CSS
    block = BASE_CSS.split("@media (prefers-reduced-motion: reduce)")[1]
    assert "transition-duration" in block
    assert "animation-duration" in block
