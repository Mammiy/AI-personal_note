"""Phase 5 · Task 3：边界用例与权限矩阵。

权限矩阵：用户 A（作者）/ 用户 B（另一位登录用户）/ 访客 C（未登录）。
所有越权返回中文提示，且响应体不得泄露他人笔记的标题与正文。
"""

import io
import re

from models import Comment, Note, NoteVersion
from utils.response import Code

TITLE_A = "甲的秘密手记"
CONTENT_A = "这段正文绝不能外泄给任何人"
# A 更新过一次后的当前标题/正文（build_world 会产生一个版本快照）
TITLE_AFTER = "改后标题"
CONTENT_AFTER = "改后正文"


def register(client, email, username):
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
    return resp.get_json()["data"]["id"]


def login_as(client, email):
    client.post("/api/auth/logout", json={})
    resp = client.post("/api/auth/login", json={"email": email, "password": "secret123"})
    assert resp.get_json()["code"] == Code.OK


def logout(client):
    client.post("/api/auth/logout", json={})


def create_note(client, **overrides):
    data = {"title": TITLE_A, "content": CONTENT_A, "tags": "秘密", "status": "published"}
    data.update(overrides)
    resp = client.post("/api/notes", json=data)
    assert resp.get_json()["code"] == Code.OK
    return resp.get_json()["data"]


def has_chinese(text):
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


# ============================================================
# 边界用例
# ============================================================


def test_boundary_each_case_returns_http_200_and_chinese(client, app, tmp_path):
    """逐条边界用例：不出现 500，message 为中文，不抛英文堆栈。"""
    register(client, "bound@example.com", "边界用户")
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    cases = [
        client.post("/api/notes", json={"title": "", "content": "", "tags": ""}),
        client.post("/api/notes", json={"title": "标" * 101, "content": "", "tags": ""}),
        client.post("/api/auth/register", json={"email": "x", "username": "无", "password": "1", "confirm": "2"}),
        client.post("/api/notes/1/comments", json={"content": "   "}),
        client.post("/api/ai/polish", json={"text": "字" * 5001}),
        client.post(
            "/api/upload",
            data={"file": (io.BytesIO(b"MZ"), "virus.exe")},
            content_type="multipart/form-data",
        ),
    ]

    for resp in cases:
        assert resp.status_code == 200, resp.status_code
        body = resp.get_json()
        assert body["code"] != Code.OK
        assert has_chinese(body["message"]), body["message"]
        assert "Traceback" not in resp.get_data(as_text=True)


def test_boundary_title_length_100_allowed_101_rejected(client):
    register(client, "len@example.com", "长度用户")

    ok = client.post("/api/notes", json={"title": "标" * 100, "content": "", "tags": ""}).get_json()
    too_long = client.post("/api/notes", json={"title": "标" * 101, "content": "", "tags": ""}).get_json()

    assert ok["code"] == Code.OK
    assert too_long["code"] == Code.PARAM_ERROR
    assert too_long["message"] == "标题不能超过 100 字"


def test_boundary_tags_truncated_to_five_and_twelve_chars(client):
    register(client, "tag@example.com", "标签用户")

    body = client.post(
        "/api/notes",
        json={"title": "标签边界", "content": "", "tags": "一,二,三,四,五,六,七"},
    ).get_json()
    assert body["data"]["tags"] == ["一", "二", "三", "四", "五"]

    tag = "这是一个超过十二个字的超长标签"
    single = client.post(
        "/api/notes", json={"title": "长标签", "content": "", "tags": tag}
    ).get_json()
    assert single["data"]["tags"] == [tag[:12]]


def test_boundary_empty_content_can_be_published(client):
    register(client, "empty@example.com", "空正文用户")

    body = client.post(
        "/api/notes", json={"title": "空正文", "content": "", "tags": "", "status": "published"}
    ).get_json()

    assert body["code"] == Code.OK
    assert body["data"]["status"] == "published"


def test_boundary_long_polish_selection_at_and_over_limit(client):
    register(client, "polish@example.com", "润色用户")

    at_limit = client.post("/api/ai/polish", json={"text": "字" * 5000}).get_json()
    over = client.post("/api/ai/polish", json={"text": "字" * 5001}).get_json()

    assert at_limit["code"] == Code.OK
    assert over["code"] == Code.PARAM_ERROR
    assert over["message"] == "选中内容过长，请分段润色"


def test_boundary_share_blank_password_removes_gate(client):
    register(client, "pw@example.com", "密码用户")
    note = create_note(client)
    token = client.put(
        f"/api/notes/{note['id']}/share", json={"is_shared": True, "password": "gate123"}
    ).get_json()["data"]["share_url"].rsplit("/", 1)[-1]

    removed = client.put(
        f"/api/notes/{note['id']}/share", json={"is_shared": True, "password": ""}
    ).get_json()

    assert removed["data"]["has_password"] is False
    logout(client)
    assert client.get(f"/api/share/{token}").get_json()["code"] == Code.OK


# ============================================================
# 权限矩阵：A / B / C
# ============================================================


def build_world(client, db_session):
    """A 拥有：一篇已发布笔记 + 一条评论 + 一个版本快照；B 为另一位登录用户。"""
    register(client, "a@example.com", "作者甲")
    note = create_note(client)
    client.post(f"/api/notes/{note['id']}/comments", json={"content": "作者自己的评论"})
    comment_id = db_session.query(Comment).one().id
    client.put(
        f"/api/notes/{note['id']}",
        json={"title": "改后标题", "content": "改后正文", "tags": "", "status": "published"},
    )
    version_id = db_session.query(NoteVersion).one().id

    register(client, "b@example.com", "路人乙")
    return {
        "note_id": note["id"],
        "comment_id": comment_id,
        "version_id": version_id,
    }


def assert_forbidden_no_leak(resp):
    body = resp.get_json()
    assert body["code"] == Code.FORBIDDEN, body
    assert body["message"] == "没有权限执行该操作"
    raw = resp.get_data(as_text=True)
    for secret in (TITLE_A, CONTENT_A, TITLE_AFTER, CONTENT_AFTER):
        assert secret not in raw, f"响应泄露了他人笔记内容：{secret}"


def test_matrix_b_cannot_read_others_note_api(client, db_session):
    world = build_world(client, db_session)  # 结束时登录态是 B

    assert_forbidden_no_leak(client.get(f"/api/notes/{world['note_id']}"))


def test_matrix_b_cannot_modify_or_delete_others_note(client, db_session):
    world = build_world(client, db_session)

    assert_forbidden_no_leak(
        client.put(f"/api/notes/{world['note_id']}", json={"title": "偷改", "content": "", "tags": ""})
    )
    assert_forbidden_no_leak(client.delete(f"/api/notes/{world['note_id']}"))
    assert db_session.query(Note).count() == 1
    assert db_session.query(Note).one().title == TITLE_AFTER


def test_matrix_b_cannot_touch_others_versions(client, db_session):
    world = build_world(client, db_session)

    assert_forbidden_no_leak(client.get(f"/api/notes/{world['note_id']}/versions"))
    assert_forbidden_no_leak(
        client.get(f"/api/notes/{world['note_id']}/versions/{world['version_id']}")
    )


def test_matrix_b_cannot_change_others_share_or_comments(client, db_session):
    world = build_world(client, db_session)

    assert_forbidden_no_leak(
        client.put(f"/api/notes/{world['note_id']}/share", json={"is_shared": True})
    )
    assert_forbidden_no_leak(
        client.put(f"/api/notes/{world['note_id']}/comments/enabled", json={"enabled": False})
    )
    assert_forbidden_no_leak(client.get(f"/api/notes/{world['note_id']}/comments"))
    assert_forbidden_no_leak(
        client.post(f"/api/notes/{world['note_id']}/comments", json={"content": "强行评论"})
    )


def test_matrix_b_cannot_delete_others_comment(client, db_session):
    world = build_world(client, db_session)

    assert_forbidden_no_leak(client.delete(f"/api/comments/{world['comment_id']}"))
    assert db_session.query(Comment).count() == 1


def test_matrix_b_cannot_favorite_others_private_note(client, db_session):
    world = build_world(client, db_session)

    assert_forbidden_no_leak(client.post(f"/api/notes/{world['note_id']}/favorite", json={}))


def test_matrix_b_visiting_others_detail_page_sees_404(client, db_session):
    world = build_world(client, db_session)

    resp = client.get(f"/notes/{world['note_id']}")

    assert resp.status_code == 404
    raw = resp.get_data(as_text=True)
    assert TITLE_A not in raw and CONTENT_A not in raw


# ---------- 访客 C ----------


def test_matrix_guest_pages_require_login(client, db_session):
    world = build_world(client, db_session)
    logout(client)

    for path in (f"/notes/{world['note_id']}", "/workspace", "/profile", "/notes", "/notes/new"):
        resp = client.get(path)
        assert resp.status_code == 302, path
        assert resp.headers["Location"].endswith("/login"), path


def test_matrix_guest_write_apis_are_unauthorized(client, db_session):
    world = build_world(client, db_session)
    logout(client)

    writes = [
        client.post("/api/notes", json={"title": "x", "content": "", "tags": ""}),
        client.put(f"/api/notes/{world['note_id']}", json={"title": "x", "content": "", "tags": ""}),
        client.delete(f"/api/notes/{world['note_id']}"),
        client.put(f"/api/notes/{world['note_id']}/share", json={"is_shared": True}),
        client.post(f"/api/notes/{world['note_id']}/favorite", json={}),
        client.post(f"/api/notes/{world['note_id']}/comments", json={"content": "x"}),
        client.delete(f"/api/comments/{world['comment_id']}"),
    ]

    for resp in writes:
        body = resp.get_json()
        assert body["code"] == Code.UNAUTHORIZED, body
        assert body["message"] == "请先登录"


def test_matrix_guest_share_closed_hides_content(client, db_session):
    world = build_world(client, db_session)
    # 切回 A 开启分享拿到令牌后关闭
    login_as(client, "a@example.com")
    token = client.put(
        f"/api/notes/{world['note_id']}/share", json={"is_shared": True}
    ).get_json()["data"]["share_url"].rsplit("/", 1)[-1]
    client.put(f"/api/notes/{world['note_id']}/share", json={"is_shared": False})
    logout(client)

    resp = client.get(f"/api/share/{token}")
    body = resp.get_json()

    assert body["code"] == Code.SHARE_CLOSED
    assert body["message"] == "分享已关闭"
    raw = resp.get_data(as_text=True)
    for secret in (TITLE_A, CONTENT_A, TITLE_AFTER, CONTENT_AFTER):
        assert secret not in raw, f"关闭的分享泄露了内容：{secret}"


def test_matrix_guest_password_gate_then_read_and_comment(client, db_session):
    world = build_world(client, db_session)
    login_as(client, "a@example.com")
    token = client.put(
        f"/api/notes/{world['note_id']}/share",
        json={"is_shared": True, "password": "gate123"},
    ).get_json()["data"]["share_url"].rsplit("/", 1)[-1]
    logout(client)

    gated = client.get(f"/api/share/{token}").get_json()
    assert gated["code"] == Code.SHARE_PASSWORD_REQUIRED
    assert gated["message"] == "该笔记需要密码才能查看"

    assert client.post(f"/api/share/{token}/verify", json={"password": "gate123"}).get_json()["code"] == Code.OK

    readable = client.get(f"/api/share/{token}").get_json()
    assert readable["code"] == Code.OK
    assert readable["data"]["title"] == TITLE_AFTER

    # 访客评论必须填昵称
    no_name = client.post(f"/api/share/{token}/comments", json={"content": "路过"}).get_json()
    assert no_name["code"] == Code.PARAM_ERROR
    assert no_name["message"] == "请填写 1 到 20 个字符的昵称"

    posted = client.post(
        f"/api/share/{token}/comments", json={"content": "路过支持", "guest_name": "路人"}
    ).get_json()
    assert posted["code"] == Code.OK
    assert posted["data"]["is_guest"] is True
    assert posted["data"]["can_delete"] is False


def test_matrix_guest_tampered_token_treated_as_closed(client):
    resp = client.get("/api/share/" + "f" * 32)
    body = resp.get_json()

    assert body["code"] == Code.SHARE_CLOSED
    assert body["message"] == "分享已关闭"


def test_matrix_guest_cannot_delete_comment(client, db_session):
    world = build_world(client, db_session)
    logout(client)

    resp = client.delete(f"/api/comments/{world['comment_id']}")

    assert resp.get_json()["code"] == Code.UNAUTHORIZED
    assert db_session.query(Comment).count() == 1
