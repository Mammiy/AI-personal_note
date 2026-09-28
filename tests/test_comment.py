"""评论 F8：开关、登录用户与访客昵称、三种删除权限。

权限矩阵：笔记作者可删任意评论；登录用户可删自己的评论；访客无删除权限。
"""

from models import Comment, Note
from utils.response import Code

TITLE = "可以评论的笔记"


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
    data = {"title": TITLE, "content": "正文", "tags": "", "status": "published"}
    data.update(overrides)
    resp = client.post("/api/notes", json=data)
    assert resp.get_json()["code"] == Code.OK
    return resp.get_json()["data"]["id"]


def share_token(client, note_id, **body):
    payload = {"is_shared": True}
    payload.update(body)
    resp = client.put(f"/api/notes/{note_id}/share", json=payload)
    assert resp.get_json()["code"] == Code.OK
    return resp.get_json()["data"]["share_url"].rsplit("/", 1)[-1]


def comments_of(client, note_id):
    return client.get(f"/api/notes/{note_id}/comments").get_json()["data"]


def guest_comments(client, token):
    return client.get(f"/api/share/{token}/comments").get_json()["data"]


# ---------- 登录用户评论 ----------


def test_logged_in_comment_shows_username(client, db_session):
    signup(client, username="小明")
    note_id = create_note(client)

    resp = client.post(f"/api/notes/{note_id}/comments", json={"content": "写得真好"})
    assert resp.get_json()["code"] == Code.OK

    data = comments_of(client, note_id)
    assert data["enabled"] is True
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["display_name"] == "小明"
    assert item["is_guest"] is False
    assert item["content"] == "写得真好"
    assert item["created_at"]
    assert set(item) == {"id", "display_name", "is_guest", "content", "created_at", "can_delete"}

    row = db_session.query(Comment).one()
    assert row.guest_name is None
    assert row.user_id is not None


def test_empty_comment_content_is_rejected(client):
    signup(client)
    note_id = create_note(client)

    resp = client.post(f"/api/notes/{note_id}/comments", json={"content": "   "})

    assert resp.get_json()["code"] == Code.PARAM_ERROR
    assert resp.get_json()["message"] == "请输入评论内容"


def test_comments_are_listed_oldest_first(client):
    signup(client)
    note_id = create_note(client)

    client.post(f"/api/notes/{note_id}/comments", json={"content": "第一条"})
    client.post(f"/api/notes/{note_id}/comments", json={"content": "第二条"})

    data = comments_of(client, note_id)
    assert [item["content"] for item in data["items"]] == ["第一条", "第二条"]


# ---------- 访客评论 ----------


def test_guest_comment_shows_nickname_and_is_flagged(client, db_session):
    signup(client)
    note_id = create_note(client)
    token = share_token(client, note_id)
    client.post("/api/auth/logout", json={})

    resp = client.post(
        f"/api/share/{token}/comments", json={"content": "路过支持", "guest_name": "路人甲"}
    )
    assert resp.get_json()["code"] == Code.OK

    data = guest_comments(client, token)
    item = data["items"][0]
    assert item["display_name"] == "路人甲"
    assert item["is_guest"] is True
    assert item["can_delete"] is False

    row = db_session.query(Comment).one()
    assert row.user_id is None


def test_guest_comment_without_nickname_is_rejected(client):
    signup(client)
    note_id = create_note(client)
    token = share_token(client, note_id)
    client.post("/api/auth/logout", json={})

    resp = client.post(f"/api/share/{token}/comments", json={"content": "没有昵称"})

    assert resp.get_json()["code"] == Code.PARAM_ERROR
    assert resp.get_json()["message"] == "请填写 1 到 20 个字符的昵称"


def test_guest_nickname_longer_than_20_chars_is_rejected(client):
    signup(client)
    note_id = create_note(client)
    token = share_token(client, note_id)
    client.post("/api/auth/logout", json={})

    resp = client.post(
        f"/api/share/{token}/comments", json={"content": "你好", "guest_name": "客" * 21}
    )

    assert resp.get_json()["code"] == Code.PARAM_ERROR
    assert resp.get_json()["message"] == "请填写 1 到 20 个字符的昵称"


def test_guest_cannot_read_comments_before_password_is_verified(client):
    signup(client)
    note_id = create_note(client)
    token = share_token(client, note_id, password="gate123")
    client.post("/api/auth/logout", json={})

    resp = client.get(f"/api/share/{token}/comments")

    assert resp.get_json()["code"] == Code.SHARE_PASSWORD_REQUIRED


def test_guest_comment_on_closed_share_is_refused(client):
    signup(client)
    note_id = create_note(client)
    token = share_token(client, note_id)
    client.put(f"/api/notes/{note_id}/share", json={"is_shared": False})
    client.post("/api/auth/logout", json={})

    resp = client.post(
        f"/api/share/{token}/comments", json={"content": "还能评论吗", "guest_name": "路人"}
    )

    assert resp.get_json()["code"] == Code.SHARE_CLOSED


# ---------- 评论开关 ----------


def test_disabled_comments_hide_history_and_refuse_new_ones(client):
    signup(client)
    note_id = create_note(client)
    client.post(f"/api/notes/{note_id}/comments", json={"content": "历史评论"})

    resp = client.put(f"/api/notes/{note_id}/comments/enabled", json={"enabled": False})
    assert resp.get_json()["data"]["enabled"] is False

    data = comments_of(client, note_id)
    assert data["items"] == []
    assert data["enabled"] is False

    denied = client.post(f"/api/notes/{note_id}/comments", json={"content": "还能发吗"})
    assert denied.get_json()["code"] == Code.FORBIDDEN
    assert denied.get_json()["message"] == "评论已关闭"


def test_reenabling_comments_restores_history(client):
    signup(client)
    note_id = create_note(client)
    client.post(f"/api/notes/{note_id}/comments", json={"content": "历史评论"})
    client.put(f"/api/notes/{note_id}/comments/enabled", json={"enabled": False})
    client.put(f"/api/notes/{note_id}/comments/enabled", json={"enabled": True})

    data = comments_of(client, note_id)

    assert data["enabled"] is True
    assert [item["content"] for item in data["items"]] == ["历史评论"]


def test_guest_comment_is_refused_when_comments_are_disabled(client):
    signup(client)
    note_id = create_note(client)
    token = share_token(client, note_id)
    client.put(f"/api/notes/{note_id}/comments/enabled", json={"enabled": False})
    client.post("/api/auth/logout", json={})

    resp = client.post(
        f"/api/share/{token}/comments", json={"content": "我来说两句", "guest_name": "路人"}
    )

    assert resp.get_json()["code"] == Code.FORBIDDEN
    assert resp.get_json()["message"] == "评论已关闭"


def test_non_author_cannot_toggle_comments(client, db_session):
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client)
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    resp = client.put(f"/api/notes/{note_id}/comments/enabled", json={"enabled": False})

    assert resp.get_json()["code"] == Code.FORBIDDEN
    assert db_session.get(Note, note_id).allow_comments is True


# ---------- 删除权限 ----------


def test_author_sees_delete_permission_on_others_comments(client, db_session):
    """作者视角下，别人与访客的评论都可删。"""
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client)
    token = share_token(client, note_id)

    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")
    client.post(
        f"/api/share/{token}/comments", json={"content": "访客留言", "guest_name": "路人甲"}
    )
    comment_id = db_session.query(Comment).one().id

    client.post("/api/auth/logout", json={})
    client.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": "secret123"}
    )

    data = comments_of(client, note_id)
    assert data["items"][0]["can_delete"] is True

    resp = client.delete(f"/api/comments/{comment_id}")
    assert resp.get_json()["code"] == Code.OK
    assert db_session.query(Comment).count() == 0


def test_logged_in_user_can_delete_own_comment(client, db_session):
    signup(client, username="小明")
    note_id = create_note(client)
    client.post(f"/api/notes/{note_id}/comments", json={"content": "我的评论"})
    comment_id = db_session.query(Comment).one().id

    data = comments_of(client, note_id)
    assert data["items"][0]["can_delete"] is True

    resp = client.delete(f"/api/comments/{comment_id}")
    assert resp.get_json()["code"] == Code.OK
    assert db_session.query(Comment).count() == 0


def test_logged_in_user_cannot_delete_others_comment(client, db_session):
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client)
    token = share_token(client, note_id)
    client.post("/api/auth/logout", json={})

    signup(client, email="other@example.com", username="路人")
    client.post(
        f"/api/share/{token}/comments", json={"content": "别人的评论", "guest_name": "路人甲"}
    )
    comment_id = db_session.query(Comment).one().id

    # 路人自己不是作者、也不是登录用户发布的评论，删除应被拒
    resp = client.delete(f"/api/comments/{comment_id}")

    assert resp.get_json()["code"] == Code.FORBIDDEN
    assert resp.get_json()["message"] == "没有权限执行该操作"
    assert db_session.query(Comment).count() == 1


def test_guest_cannot_delete_any_comment(client, db_session):
    signup(client)
    note_id = create_note(client)
    token = share_token(client, note_id)
    client.post("/api/auth/logout", json={})
    client.post(
        f"/api/share/{token}/comments", json={"content": "访客评论", "guest_name": "路人甲"}
    )
    comment_id = db_session.query(Comment).one().id

    resp = client.delete(f"/api/comments/{comment_id}")

    assert resp.get_json()["code"] == Code.UNAUTHORIZED
    assert db_session.query(Comment).count() == 1

    data = guest_comments(client, token)
    assert data["items"][0]["can_delete"] is False


def test_deleting_missing_comment_is_forbidden(client):
    signup(client)

    resp = client.delete("/api/comments/9999")

    assert resp.get_json()["code"] == Code.FORBIDDEN


# ---------- 越权与请求格式 ----------


def test_anonymous_comment_on_note_api_is_unauthorized(client):
    resp = client.post("/api/notes/1/comments", json={"content": "匿名"})

    assert resp.get_json()["code"] == Code.UNAUTHORIZED


def test_non_author_cannot_read_or_post_note_comments(client, db_session):
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client)
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    assert client.get(f"/api/notes/{note_id}/comments").get_json()["code"] == Code.FORBIDDEN

    resp = client.post(f"/api/notes/{note_id}/comments", json={"content": "强行评论"})
    assert resp.get_json()["code"] == Code.FORBIDDEN
    assert db_session.query(Comment).count() == 0


def test_comment_write_requires_json_body(client):
    signup(client)
    note_id = create_note(client)

    resp = client.post(
        f"/api/notes/{note_id}/comments",
        data="content=hi",
        content_type="application/x-www-form-urlencoded",
    )

    assert resp.get_json()["code"] == Code.PARAM_ERROR
    assert resp.get_json()["message"] == "请求格式不正确"


def test_guest_comment_requires_json_body(client):
    signup(client)
    note_id = create_note(client)
    token = share_token(client, note_id)
    client.post("/api/auth/logout", json={})

    resp = client.post(
        f"/api/share/{token}/comments",
        data="content=hi",
        content_type="application/x-www-form-urlencoded",
    )

    assert resp.get_json()["code"] == Code.PARAM_ERROR
