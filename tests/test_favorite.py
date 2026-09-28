"""收藏 F9：切换幂等、列表按收藏时间倒序、允许收藏自己的笔记。"""

from models import Favorite, Note
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


def create_note(client, title="被收藏的笔记", **overrides):
    data = {"title": title, "content": "正文", "tags": "生活", "status": "published"}
    data.update(overrides)
    resp = client.post("/api/notes", json=data)
    assert resp.get_json()["code"] == Code.OK
    return resp.get_json()["data"]["id"]


def favorites_of(client):
    return client.get("/api/favorites").get_json()["data"]


# ---------- 收藏与取消 ----------


def test_favoriting_a_note_makes_it_appear_in_the_list(client, db_session):
    signup(client)
    note_id = create_note(client)

    resp = client.post(f"/api/notes/{note_id}/favorite", json={})

    assert resp.get_json()["code"] == Code.OK
    assert db_session.query(Favorite).count() == 1

    items = favorites_of(client)["items"]
    assert len(items) == 1
    assert items[0]["note_id"] == note_id
    assert items[0]["title"] == "被收藏的笔记"
    assert items[0]["status"] == "published"
    assert set(items[0]) == {"note_id", "title", "status", "updated_at", "favorited_at"}


def test_favoriting_twice_creates_only_one_row(client, db_session):
    signup(client)
    note_id = create_note(client)

    client.post(f"/api/notes/{note_id}/favorite", json={})
    resp = client.post(f"/api/notes/{note_id}/favorite", json={})

    assert resp.get_json()["code"] == Code.OK
    assert db_session.query(Favorite).count() == 1


def test_unfavoriting_removes_it_from_the_list(client, db_session):
    signup(client)
    note_id = create_note(client)
    client.post(f"/api/notes/{note_id}/favorite", json={})

    resp = client.delete(f"/api/notes/{note_id}/favorite")

    assert resp.get_json()["code"] == Code.OK
    assert db_session.query(Favorite).count() == 0
    assert favorites_of(client)["items"] == []


def test_unfavoriting_a_note_that_is_not_favorited_is_idempotent(client, db_session):
    signup(client)
    note_id = create_note(client)

    resp = client.delete(f"/api/notes/{note_id}/favorite")

    assert resp.get_json()["code"] == Code.OK
    assert db_session.query(Favorite).count() == 0


def test_user_can_favorite_own_note(client, db_session):
    user_id = signup(client)
    note_id = create_note(client)

    resp = client.post(f"/api/notes/{note_id}/favorite", json={})

    assert resp.get_json()["code"] == Code.OK
    row = db_session.query(Favorite).one()
    assert row.user_id == user_id


# ---------- 列表顺序 ----------


def test_favorites_are_ordered_by_favorited_time_desc(client, db_session):
    signup(client)
    first = create_note(client, title="先收藏的")
    second = create_note(client, title="后收藏的")

    client.post(f"/api/notes/{first}/favorite", json={})
    client.post(f"/api/notes/{second}/favorite", json={})

    titles = [item["title"] for item in favorites_of(client)["items"]]

    assert titles == ["后收藏的", "先收藏的"]


def test_toggling_off_and_on_keeps_the_latest_order(client, db_session):
    signup(client)
    first = create_note(client, title="先收藏的")
    second = create_note(client, title="后收藏的")

    client.post(f"/api/notes/{first}/favorite", json={})
    client.post(f"/api/notes/{second}/favorite", json={})
    client.delete(f"/api/notes/{first}/favorite")
    client.post(f"/api/notes/{first}/favorite", json={})

    titles = [item["title"] for item in favorites_of(client)["items"]]

    assert titles == ["先收藏的", "后收藏的"]


def test_favorites_only_contain_current_users_rows(client):
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client, title="作者的笔记")
    client.post(f"/api/notes/{note_id}/favorite", json={})
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    assert favorites_of(client)["items"] == []


def test_favorite_count_is_reflected_in_workspace_summary(client):
    signup(client)
    note_id = create_note(client)
    client.post(f"/api/notes/{note_id}/favorite", json={})

    data = client.get("/api/workspace/summary").get_json()["data"]

    assert data["favorite_count"] == 1


# ---------- 详情接口与越权 ----------


def test_detail_reports_whether_the_note_is_favorited(client):
    signup(client)
    note_id = create_note(client)

    assert client.get(f"/api/notes/{note_id}").get_json()["data"]["is_favorited"] is False

    client.post(f"/api/notes/{note_id}/favorite", json={})

    assert client.get(f"/api/notes/{note_id}").get_json()["data"]["is_favorited"] is True


def test_anonymous_cannot_favorite(client):
    resp = client.post("/api/notes/1/favorite", json={})

    assert resp.get_json()["code"] == Code.UNAUTHORIZED


def test_favorites_list_requires_login(client):
    assert client.get("/api/favorites").get_json()["code"] == Code.UNAUTHORIZED


def test_favoriting_requires_json_body(client, db_session):
    signup(client)
    note_id = create_note(client)

    resp = client.post(
        f"/api/notes/{note_id}/favorite",
        data="x=1",
        content_type="application/x-www-form-urlencoded",
    )

    assert resp.get_json()["code"] == Code.PARAM_ERROR
    assert db_session.query(Favorite).count() == 0


# ---------- 数据隔离 ----------


def test_cannot_favorite_another_users_private_note(client, db_session):
    """凭 id 猜到他人草稿也不得收藏，否则收藏列表会泄露草稿标题。"""
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client, title="作者的草稿", status="draft")
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    resp = client.post(f"/api/notes/{note_id}/favorite", json={})

    assert resp.get_json()["code"] == Code.FORBIDDEN
    assert resp.get_json()["message"] == "没有权限执行该操作"
    assert db_session.query(Favorite).count() == 0


def test_can_favorite_another_users_shared_note(client, db_session):
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client, title="作者的分享")
    client.put(f"/api/notes/{note_id}/share", json={"is_shared": True})
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    resp = client.post(f"/api/notes/{note_id}/favorite", json={})

    assert resp.get_json()["code"] == Code.OK
    assert [item["title"] for item in favorites_of(client)["items"]] == ["作者的分享"]


def test_favorites_drop_notes_that_stopped_being_shared(client):
    """分享关闭后，别人的收藏列表不该继续展示这篇笔记。"""
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client, title="作者的分享")
    client.put(f"/api/notes/{note_id}/share", json={"is_shared": True})
    client.post("/api/auth/logout", json={})

    signup(client, email="other@example.com", username="路人")
    client.post(f"/api/notes/{note_id}/favorite", json={})
    assert len(favorites_of(client)["items"]) == 1

    client.post("/api/auth/logout", json={})
    client.post("/api/auth/login", json={"email": "owner@example.com", "password": "secret123"})
    client.put(f"/api/notes/{note_id}/share", json={"is_shared": False})
    client.post("/api/auth/logout", json={})
    client.post("/api/auth/login", json={"email": "other@example.com", "password": "secret123"})

    assert favorites_of(client)["items"] == []


# ---------- 收藏与删除的联动 ----------


def test_deleting_a_note_drops_its_favorites(client, db_session):
    signup(client)
    note_id = create_note(client)
    client.post(f"/api/notes/{note_id}/favorite", json={})

    client.delete(f"/api/notes/{note_id}")

    assert db_session.query(Favorite).count() == 0
    assert db_session.query(Note).count() == 0
    assert favorites_of(client)["items"] == []
