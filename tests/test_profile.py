"""个人主页 F10：个人信息只读、收藏列表、笔记历史入口。"""

from utils.response import Code


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


def create_note(client, title="一篇笔记", **overrides):
    data = {"title": title, "content": "正文", "tags": "生活", "status": "draft"}
    data.update(overrides)
    resp = client.post("/api/notes", json=data)
    assert resp.get_json()["code"] == Code.OK
    return resp.get_json()["data"]["id"]


def profile_of(client):
    return client.get("/api/profile")


# ---------- 个人信息 ----------


def test_profile_returns_user_info_favorites_and_notes(client):
    signup(client, email="writer@example.com", username="写作者")
    note_id = create_note(client, title="我的笔记")
    client.post(f"/api/notes/{note_id}/favorite", json={})

    body = profile_of(client).get_json()

    assert body["code"] == Code.OK
    data = body["data"]
    assert set(data) == {"user", "favorites", "notes"}

    assert data["user"]["username"] == "写作者"
    assert data["user"]["email"] == "writer@example.com"
    assert data["user"]["created_at"]
    assert set(data["user"]) == {"username", "email", "created_at"}

    assert [item["note_id"] for item in data["favorites"]] == [note_id]
    assert data["notes"] == [{"id": note_id, "title": "我的笔记"}]


def test_profile_favorites_are_empty_by_default(client):
    signup(client)
    create_note(client)

    data = profile_of(client).get_json()["data"]

    assert data["favorites"] == []
    assert len(data["notes"]) == 1


def test_profile_requires_login(client):
    assert profile_of(client).get_json()["code"] == Code.UNAUTHORIZED


def test_profile_only_shows_current_users_data(client):
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client, title="作者的笔记")
    client.post(f"/api/notes/{note_id}/favorite", json={})
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")
    create_note(client, title="路人的笔记")

    data = profile_of(client).get_json()["data"]

    assert data["user"]["username"] == "路人"
    assert data["favorites"] == []
    assert [item["title"] for item in data["notes"]] == ["路人的笔记"]


# ---------- 个人主页页面 ----------


def test_profile_page_requires_login(client):
    resp = client.get("/profile")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_page_renders_three_sections(client):
    signup(client)

    resp = client.get("/profile")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert html.count("<h1") == 1
    for copy in ("个人主页", "个人信息", "我的收藏", "笔记历史", "还没有收藏的笔记"):
        assert copy in html
    assert "profile.js" in html
