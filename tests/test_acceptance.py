"""Phase 5 · Task 1：F1–F12 与 R1–R3 验收走查的可执行证据。

已在 tests/test_auth.py、test_note.py、test_share.py、test_comment.py、test_favorite.py、
test_profile.py、test_ai.py、test_upload.py、test_response.py、test_pages.py 覆盖的条目
不在此重复；这里补的是「尚无自动化断言」的验收点，以及 R1–R3 三条全局规范。
"""

import re
from pathlib import Path

import pytest

from utils.response import Code

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "templates"
JS = ROOT / "static" / "js"
CSS = ROOT / "static" / "css"
VENDOR = JS / "vendor"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def register(client, email="walker@example.com", username="行走者"):
    resp = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "secret123",
            "confirm": "secret123",
        },
    )
    assert resp.get_json()["code"] == Code.OK
    return resp


def create_note(client, **overrides):
    data = {"title": "一篇验收笔记", "content": "正文", "tags": "验收", "status": "draft"}
    data.update(overrides)
    resp = client.post("/api/notes", json=data)
    assert resp.get_json()["code"] == Code.OK
    return resp.get_json()["data"]


# ---------- F1 注册 ----------


def test_f1_authed_user_visiting_register_redirects_to_workspace(client):
    register(client)

    resp = client.get("/register")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/workspace")


def test_f1_register_diagnostic_messages_are_chinese(client):
    """失败信息全部是中文，不出现英文堆栈。"""
    cases = [
        ({"email": "", "username": "甲", "password": "secret123", "confirm": "secret123"}, "请填写邮箱"),
        ({"email": "bad", "username": "甲", "password": "secret123", "confirm": "secret123"}, "邮箱格式不正确"),
        ({"email": "a@b.com", "username": "甲", "password": "secret123", "confirm": "secret123"}, "用户名"),
        ({"email": "a@b.com", "username": "甲乙", "password": "123", "confirm": "123"}, "密码"),
        ({"email": "a@b.com", "username": "甲乙", "password": "secret123", "confirm": "other1"}, "两次输入的密码不一致"),
    ]
    for payload, expected in cases:
        body = client.post("/api/auth/register", json=payload).get_json()
        assert body["code"] == Code.PARAM_ERROR
        assert expected in body["message"]


# ---------- F2 登录 ----------


def test_f2_session_cookie_is_browser_session_only(client):
    """会话级登录：不写 Expires/Max-Age，关闭浏览器即失效。"""
    resp = register(client)
    cookies = " ".join(resp.headers.getlist("Set-Cookie"))

    assert "Expires=" not in cookies
    assert "Max-Age=" not in cookies


def test_f2_session_cookie_is_httponly_and_lax(client):
    resp = register(client)
    cookies = " ".join(resp.headers.getlist("Set-Cookie"))

    assert "HttpOnly" in cookies
    assert "SameSite=Lax" in cookies


def test_f2_logout_returns_to_home(client):
    """退出按钮由 base.html 统一跳回主页。"""
    assert 'window.location.href = "/"' in read(TPL / "base.html")


# ---------- F3 主页 / F4 工作台 / F5 笔记 ----------


def test_f3_home_hero_uses_home_background():
    css = read(CSS / "pages.css")
    assert 'url("../img/home-bg.jpg")' in css


def test_f4_workspace_zero_state_copy_is_present():
    html = read(TPL / "workspace.html")
    assert "还没有文章，点" in html
    assert "新建文章" in html
    assert "我的文章" in html


def test_f5_toolbar_has_ten_actions():
    actions = re.findall(r'data-action="([^"]+)"', read(TPL / "note_edit.html"))
    assert actions == ["h1", "h2", "bold", "italic", "quote", "code", "ul", "ol", "link", "image"]


def test_f5_detail_page_has_comment_count_placeholder():
    assert 'id="comment-count"' in read(TPL / "note_detail.html")


# ---------- F6 列表 / F7 分享 / F8 评论 ----------


def test_f6_list_page_has_two_distinct_empty_containers():
    html = read(TPL / "notes.html")
    assert 'id="empty-state"' in html and 'id="empty-text"' in html
    assert "清空筛选" in html


def test_f7_copy_success_message_is_copied_link():
    assert "已复制链接" in read(JS / "ui.js")


def test_f7_share_page_renders_all_three_state_cards():
    html = read(TPL / "share.html")
    for marker in ("share-gate-card", "share-read", "share-comment-card"):
        assert f'id="{marker}"' in html


def test_f8_comment_switch_and_guest_source_badge_exist():
    assert 'id="comment-switch"' in read(TPL / "note_detail.html")
    # 访客来源标注在 note_detail.js / share.js 中渲染为「访客」徽标
    assert '"访客"' in read(JS / "note_detail.js")
    assert '"访客"' in read(JS / "share.js")


# ---------- F9 收藏 / F10 个人主页 / F11 AI / F12 关于 ----------


def test_f9_favorite_toggle_feedback_in_wired_detail_script():
    js = read(JS / "note_detail.js")
    assert '"已收藏"' in js and '"已取消收藏"' in js
    assert "/favorite" in js


def test_f10_versions_are_read_only_no_restore_route():
    source = read(ROOT / "routes" / "api_notes.py")
    assert "restore" not in source
    assert '@bp.get("/api/notes/<int:id>/versions/<int:vid>")' in source


def test_f11_ai_polish_entry_wired_on_editor_page():
    html = read(TPL / "note_edit.html")
    assert "ai_polish.js" in html
    assert 'id="ctx-menu"' in html
    assert 'id="ai-polish-modal"' in html


def test_f12_about_page_has_four_sections_and_no_form():
    html = read(TPL / "about.html")
    for section in ("项目简介", "功能概览", "技术栈", "使用提示"):
        assert section in html
    assert "<form" not in html


# ---------- R1 统一错误响应 ----------


def test_r1_sampled_endpoints_share_envelope(client):
    register(client)
    note = create_note(client)
    token = "a" * 32

    probes = [
        client.get("/api/health"),
        client.get("/api/notes"),
        client.get("/api/auth/me"),
        client.get(f"/api/notes/{note['id']}"),
        client.get(f"/api/share/{token}"),
        client.get("/api/not-a-real-endpoint"),
    ]

    for resp in probes:
        body = resp.get_json()
        assert set(body.keys()) == {"code", "message", "data"}
        assert "charset=utf-8" in resp.headers["Content-Type"]
        if body["code"] != Code.OK:
            assert body["data"] is None
            # message 必须是中文提示，不含英文堆栈/路径
            assert re.search(r"[\u4e00-\u9fff]", body["message"])
            assert "Traceback" not in body["message"]


def test_r1_unauthorized_and_forbidden_return_chinese(client):
    register(client, email="a@example.com", username="甲用户")
    register(client, email="b@example.com", username="乙用户")  # 覆盖不了 A 的笔记

    foreign = client.put("/api/notes/9999", json={"title": "x", "content": "", "tags": ""})
    assert foreign.get_json()["code"] == Code.FORBIDDEN
    assert foreign.get_json()["message"] == "没有权限执行该操作"


def test_r1_unexpected_exception_returns_server_busy(client, app):
    @app.get("/api/_accept_boom")
    def boom():
        raise RuntimeError("boom-internal-xyz")

    resp = client.get("/api/_accept_boom")
    body = resp.get_json()

    assert body["code"] == Code.SERVER_ERROR
    assert body["message"] == "服务器繁忙，请稍后重试"
    assert "boom-internal-xyz" not in resp.get_data(as_text=True)


# ---------- R2 依赖管理 ----------


def test_r2_requirements_are_pinned_with_double_equals():
    lines = [
        line.strip()
        for line in read(ROOT / "requirements.txt").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines, "requirements.txt 不能为空"
    for line in lines:
        assert re.fullmatch(r"[A-Za-z0-9_.\-]+==[^\s]+", line), f"未锁定精确版本：{line}"


def test_r2_readme_documents_tsinghua_mirror():
    readme = read(ROOT / "README.md")
    assert "pypi.tuna.tsinghua.edu.cn" in readme


def test_r2_vendor_libs_exist_and_are_local():
    assert (VENDOR / "marked.umd.js").exists()
    assert (VENDOR / "purify.min.js").exists()

    base_html = read(TPL / "base.html")
    assert "vendor/marked.umd.js" in base_html
    assert "vendor/purify.min.js" in base_html


EXTERNAL_RE = re.compile(
    r"https?://|cdn\.jsdelivr|cdnjs|fonts\.googleapis|unpkg\.com|//cdn\.",
    re.IGNORECASE,
)


def test_r2_no_external_cdn_references_in_pages_or_own_assets():
    scanned = list(TPL.glob("*.html")) + list(CSS.glob("*.css")) + list(JS.glob("*.js"))
    offenders = []
    for path in scanned:
        text = read(path)
        for match in EXTERNAL_RE.finditer(text):
            offenders.append(f"{path.name}: {match.group(0)}")

    assert not offenders, f"发现外部地址引用：{offenders}"


# ---------- R3 字符编码 ----------


def test_r3_no_gbk_in_code():
    targets = [
        ROOT / "app.py",
        ROOT / "config.py",
        ROOT / "models.py",
        *sorted((ROOT / "routes").glob("*.py")),
        *sorted((ROOT / "services").glob("*.py")),
        *sorted((ROOT / "utils").glob("*.py")),
    ]
    for path in targets:
        assert "gbk" not in read(path).lower(), f"{path.name} 出现 GBK 字样"


SPECIAL_CONTENT = (
    "# 标题\n"
    "中文内容 with emoji 😀🎉\n"
    "反引号 `code`、星号 **加粗**、井号 #、竖线 |、尖括号 <script>alert(1)</script>\n"
    "- 列表项一\n- 列表项二\n"
)


def test_r3_special_characters_round_trip_through_save_detail_and_share(client):
    register(client)
    note = create_note(client, content=SPECIAL_CONTENT, status="published")
    assert note["content"] == SPECIAL_CONTENT

    # 详情接口原样回传
    detail = client.get(f"/api/notes/{note['id']}")
    assert "charset=utf-8" in detail.headers["Content-Type"]
    assert detail.get_json()["data"]["note"]["content"] == SPECIAL_CONTENT

    # 开启分享后访客读取，同样原样回传且声明 UTF-8
    share = client.put(f"/api/notes/{note['id']}/share", json={"is_shared": True}).get_json()
    token = share["data"]["share_url"].rsplit("/", 1)[-1]
    client.post("/api/auth/logout", json={})

    public = client.get(f"/api/share/{token}")
    assert "charset=utf-8" in public.headers["Content-Type"]
    body = public.get_json()["data"]
    assert body["content"] == SPECIAL_CONTENT
    # 无乱码：emoji 与中文必须能被解出
    assert "😀" in body["content"]
    assert "中文内容" in body["content"]


def test_r3_page_responses_declare_utf8(client):
    for path in ("/", "/about", "/login"):
        resp = client.get(path)
        assert "charset=utf-8" in resp.headers["Content-Type"].lower()
