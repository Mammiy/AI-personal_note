"""分享：开关、令牌、密码门与越权。

F7：开启分享生成不可预测令牌；关闭后对外一律 SHARE_CLOSED 且不泄露标题与正文；
密码只存哈希，验证通过前的任何响应都不含笔记内容。
"""

from models import Note
from utils.response import Code

TITLE = "独享的旅行手记"
CONTENT = "这是一段绝不外泄的正文内容"


def signup(client, email="writer@example.com", username="写作者"):
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


def create_note(client, **overrides):
    data = {"title": TITLE, "content": CONTENT, "tags": "生活", "status": "published"}
    data.update(overrides)
    resp = client.post("/api/notes", json=data)
    assert resp.get_json()["code"] == Code.OK
    return resp.get_json()["data"]["id"]


def set_share(client, note_id, **body):
    payload = {"is_shared": True}
    payload.update(body)
    return client.put(f"/api/notes/{note_id}/share", json=payload)


def read_share(client, token):
    return client.get("/api/share/" + token)


def token_of(client, note_id, **body):
    return set_share(client, note_id, **body).get_json()["data"]["share_url"].rsplit("/", 1)[-1]


# ---------- 开启分享与令牌 ----------


def test_enable_share_generates_32_char_token(client, db_session):

    signup(client)
    note_id = create_note(client)

    resp = set_share(client, note_id)
    body = resp.get_json()

    assert body["code"] == Code.OK
    assert body["data"]["is_shared"] is True
    assert body["data"]["has_password"] is False
    assert body["data"]["share_url"].startswith("/s/")

    token = body["data"]["share_url"].rsplit("/", 1)[-1]
    assert len(token) == 32

    note = db_session.get(Note, note_id)
    assert note.share_token == token
    assert note.is_shared is True


def test_new_note_has_no_token_until_shared(client, db_session):

    signup(client)
    note_id = create_note(client)

    note = db_session.get(Note, note_id)
    assert note.share_token is None
    assert note.is_shared is False


def test_reopening_share_keeps_the_same_token(client, db_session):

    signup(client)
    note_id = create_note(client)

    first = token_of(client, note_id)
    set_share(client, note_id, is_shared=False)
    second_url = set_share(client, note_id, is_shared=True).get_json()["data"]["share_url"]

    assert second_url == "/s/" + first
    assert db_session.get(Note, note_id).share_token == first


# ---------- 公开分享的访客阅读 ----------


def test_guest_can_read_shared_note_without_login(client):
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id)
    client.post("/api/auth/logout", json={})

    body = read_share(client, token).get_json()

    assert body["code"] == Code.OK
    assert body["data"]["title"] == TITLE
    assert body["data"]["content"] == CONTENT
    assert body["data"]["allow_comments"] is True
    assert set(body["data"]) == {"title", "content", "updated_at", "allow_comments"}


def test_closed_share_returns_share_closed_without_content(client):
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id)
    set_share(client, note_id, is_shared=False)
    client.post("/api/auth/logout", json={})

    resp = read_share(client, token)
    body = resp.get_json()

    assert body["code"] == Code.SHARE_CLOSED
    assert body["message"] == "分享已关闭"
    assert body["data"] is None
    assert TITLE not in resp.get_data(as_text=True)
    assert CONTENT not in resp.get_data(as_text=True)


def test_share_page_skeleton_leaks_no_note_content(client):
    """骨架页必须先于内容返回：即使分享是开启的，HTML 里也不该有标题与正文。"""
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id)
    client.post("/api/auth/logout", json={})

    resp = client.get("/s/" + token)
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert html.count("<h1") == 1
    assert token in html
    assert TITLE not in html
    assert CONTENT not in html


def test_closed_share_page_html_has_no_note_information(client):
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id)
    set_share(client, note_id, is_shared=False)
    client.post("/api/auth/logout", json={})

    html = client.get("/s/" + token).get_data(as_text=True)

    assert "分享已关闭" in html
    assert TITLE not in html
    assert CONTENT not in html
    assert "分享笔记" in html


def test_unknown_token_returns_share_closed(client):
    resp = read_share(client, "a" * 32)
    body = resp.get_json()

    assert body["code"] == Code.SHARE_CLOSED
    assert body["data"] is None


# ---------- 密码门 ----------


def test_password_protected_share_requires_password_before_any_content(client):
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id, password="gate123")
    client.post("/api/auth/logout", json={})

    resp = read_share(client, token)
    body = resp.get_json()

    assert body["code"] == Code.SHARE_PASSWORD_REQUIRED
    assert body["message"] == "该笔记需要密码才能查看"
    assert body["data"] is None
    raw = resp.get_data(as_text=True)
    assert TITLE not in raw
    assert CONTENT not in raw


def test_setting_password_reports_has_password_and_stores_hash_only(client, db_session):

    signup(client)
    note_id = create_note(client)

    body = set_share(client, note_id, password="gate123").get_json()

    assert body["data"]["has_password"] is True
    note = db_session.get(Note, note_id)
    assert note.share_password_hash
    assert "gate123" not in note.share_password_hash


def test_correct_password_unlocks_the_note(client):
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id, password="gate123")
    client.post("/api/auth/logout", json={})

    verify = client.post(f"/api/share/{token}/verify", json={"password": "gate123"})
    assert verify.get_json()["code"] == Code.OK

    body = read_share(client, token).get_json()
    assert body["code"] == Code.OK
    assert body["data"]["content"] == CONTENT


def test_wrong_password_is_rejected_and_note_stays_locked(client):
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id, password="gate123")
    client.post("/api/auth/logout", json={})

    resp = client.post(f"/api/share/{token}/verify", json={"password": "错密码"})
    body = resp.get_json()

    assert body["code"] == Code.SHARE_PASSWORD_WRONG
    assert body["message"] == "密码错误，请重新输入"
    assert read_share(client, token).get_json()["code"] == Code.SHARE_PASSWORD_REQUIRED


def test_blank_password_removes_the_gate(client):
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id, password="gate123")

    body = set_share(client, note_id, password="").get_json()

    assert body["data"]["has_password"] is False
    client.post("/api/auth/logout", json={})
    assert read_share(client, token).get_json()["data"]["content"] == CONTENT


def test_omitted_password_keeps_the_existing_gate(client):
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id, password="gate123")

    body = set_share(client, note_id, is_shared=True).get_json()

    assert body["data"]["has_password"] is True
    client.post("/api/auth/logout", json={})
    assert read_share(client, token).get_json()["code"] == Code.SHARE_PASSWORD_REQUIRED


def test_verify_requires_json_body(client):
    signup(client)
    note_id = create_note(client)
    token = token_of(client, note_id, password="gate123")
    client.post("/api/auth/logout", json={})

    resp = client.post(
        f"/api/share/{token}/verify",
        data="password=gate123",
        content_type="application/x-www-form-urlencoded",
    )

    assert resp.get_json()["code"] == Code.PARAM_ERROR
    assert resp.get_json()["message"] == "请求格式不正确"


# ---------- 越权 ----------


def test_non_author_cannot_change_share_settings(client, db_session):

    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client)
    token = token_of(client, note_id)
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    resp = set_share(client, note_id, is_shared=False)
    body = resp.get_json()

    assert body["code"] == Code.FORBIDDEN
    assert body["message"] == "没有权限执行该操作"
    note = db_session.get(Note, note_id)
    assert note.is_shared is True
    assert note.share_token == token


def test_anonymous_cannot_change_share_settings(client):
    signup(client)
    note_id = create_note(client)
    client.post("/api/auth/logout", json={})

    resp = set_share(client, note_id)

    assert resp.get_json()["code"] == Code.UNAUTHORIZED


def test_share_settings_require_json_body(client):
    signup(client)
    note_id = create_note(client)

    resp = client.put(
        f"/api/notes/{note_id}/share",
        data="is_shared=1",
        content_type="application/x-www-form-urlencoded",
    )

    assert resp.get_json()["code"] == Code.PARAM_ERROR
