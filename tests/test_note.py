"""笔记核心：新建 / 更新 / 版本快照 / 发布 / 标签 / 越权 / 删除级联。"""

from datetime import datetime, timedelta

from models import Comment, Favorite, Note, NoteVersion
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


def create_note(client, **overrides):
    data = {"title": "第一篇笔记", "content": "正文内容", "tags": "生活,工作", "status": "draft"}
    data.update(overrides)
    return client.post("/api/notes", json=data)


# ---------- 新建 ----------


def test_create_draft_returns_envelope_and_persists(client, db_session):
    user_id = signup(client)

    resp = create_note(client)
    body = resp.get_json()

    assert body["code"] == Code.OK
    assert body["data"]["status"] == "draft"
    assert body["data"]["tags"] == ["生活", "工作"]
    assert body["data"]["title"] == "第一篇笔记"
    assert body["data"]["content"] == "正文内容"
    assert body["data"]["id"] > 0
    assert set(body["data"]) == {
        "id",
        "title",
        "content",
        "tags",
        "status",
        "created_at",
        "updated_at",
        "published_at",
    }

    note = db_session.query(Note).one()
    assert note.title == "第一篇笔记"
    assert note.user_id == user_id


def test_create_draft_generates_no_version(client, db_session):
    signup(client)
    create_note(client)

    assert db_session.query(NoteVersion).count() == 0


def test_create_published_note_sets_published_at(client, db_session):
    signup(client)

    resp = create_note(client, status="published")
    body = resp.get_json()

    assert body["code"] == Code.OK
    assert body["data"]["status"] == "published"

    note = db_session.query(Note).one()
    assert note.published_at is not None


# ---------- 标题与标签校验 ----------


def test_empty_title_is_rejected(client):
    signup(client)

    resp = create_note(client, title="")
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "请填写标题"


def test_blank_title_is_rejected(client):
    signup(client)

    resp = create_note(client, title="   ")
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "请填写标题"


def test_title_over_100_chars_is_rejected(client):
    signup(client)

    resp = create_note(client, title="标" * 101)
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "标题不能超过 100 字"


def test_empty_content_is_allowed(client):
    signup(client)

    resp = create_note(client, content="")

    assert resp.get_json()["code"] == Code.OK


def test_tags_are_truncated_to_five(client):
    signup(client)

    resp = create_note(client, tags="一,二,三,四,五,六,七")

    assert resp.get_json()["data"]["tags"] == ["一", "二", "三", "四", "五"]


def test_single_tag_is_truncated_to_twelve_chars(client):
    signup(client)

    resp = create_note(client, tags="这是一个非常非常长的标签名称")

    assert resp.get_json()["data"]["tags"] == ["这是一个非常非常长的标签"]


def test_tags_are_deduped_and_support_chinese_comma(client):
    signup(client)

    resp = create_note(client, tags="生活，工作, 生活 ,, 随笔")

    assert resp.get_json()["data"]["tags"] == ["生活", "工作", "随笔"]


# ---------- 更新与版本快照 ----------


def test_update_creates_one_version_with_previous_content(client, db_session):
    signup(client)
    note_id = create_note(client).get_json()["data"]["id"]

    resp = client.put(
        f"/api/notes/{note_id}",
        json={"title": "改后的标题", "content": "改后的正文", "tags": "随笔", "status": "draft"},
    )
    body = resp.get_json()

    assert body["code"] == Code.OK
    assert body["data"]["title"] == "改后的标题"

    versions = db_session.query(NoteVersion).all()
    assert len(versions) == 1
    # 版本记录保存的是更新前的内容
    assert versions[0].title == "第一篇笔记"
    assert versions[0].content == "正文内容"
    assert versions[0].tags == "生活,工作"
    assert versions[0].note_id == note_id


def test_update_keeps_published_at_unchanged_on_second_save(client, db_session):
    signup(client)
    note_id = create_note(client, status="published").get_json()["data"]["id"]
    first_published_at = db_session.query(Note).one().published_at

    client.put(
        f"/api/notes/{note_id}",
        json={"title": "再改一次", "content": "新正文", "tags": "", "status": "published"},
    )

    note = db_session.query(Note).one()
    assert note.published_at == first_published_at
    assert note.status == "published"


def test_publish_draft_writes_published_at_once(client, db_session):
    signup(client)
    note_id = create_note(client).get_json()["data"]["id"]
    assert db_session.query(Note).one().published_at is None

    resp = client.put(
        f"/api/notes/{note_id}",
        json={"title": "第一篇笔记", "content": "正文内容", "tags": "生活", "status": "published"},
    )

    assert resp.get_json()["data"]["status"] == "published"
    published_at = db_session.query(Note).one().published_at
    assert published_at is not None


# ---------- 越权与请求格式 ----------


def test_updating_other_users_note_is_forbidden(client, db_session):
    owner_id = signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client).get_json()["data"]["id"]
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    resp = client.put(f"/api/notes/{note_id}", json={"title": "偷改标题", "content": "", "tags": ""})
    body = resp.get_json()

    assert body["code"] == Code.FORBIDDEN
    assert body["message"] == "没有权限执行该操作"
    assert db_session.query(Note).one().title == "第一篇笔记"
    assert db_session.query(Note).one().user_id == owner_id


def test_deleting_other_users_note_is_forbidden(client, db_session):
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client).get_json()["data"]["id"]
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    resp = client.delete(f"/api/notes/{note_id}")

    assert resp.get_json()["code"] == Code.FORBIDDEN
    assert db_session.query(Note).count() == 1


def test_form_encoded_note_request_is_rejected(client):
    signup(client)

    resp = client.post(
        "/api/notes",
        data="title=x",
        content_type="application/x-www-form-urlencoded",
    )

    assert resp.get_json()["code"] == Code.PARAM_ERROR
    assert resp.get_json()["message"] == "请求格式不正确"


def test_anonymous_write_is_unauthorized(client):
    resp = create_note(client)

    assert resp.get_json()["code"] == Code.UNAUTHORIZED


# ---------- 删除与级联 ----------


def test_delete_note_removes_comments_favorites_and_versions(client, db_session):
    signup(client)
    note_id = create_note(client).get_json()["data"]["id"]
    client.put(
        f"/api/notes/{note_id}",
        json={"title": "改后", "content": "改后正文", "tags": "", "status": "draft"},
    )

    db_session.add(Comment(note_id=note_id, guest_name="访客", content="很棒"))
    db_session.add(Favorite(user_id=1, note_id=note_id))
    db_session.commit()
    assert db_session.query(NoteVersion).count() == 1

    resp = client.delete(f"/api/notes/{note_id}")

    assert resp.get_json()["code"] == Code.OK
    assert db_session.query(Note).count() == 0
    assert db_session.query(Comment).count() == 0
    assert db_session.query(Favorite).count() == 0
    assert db_session.query(NoteVersion).count() == 0


# ---------- 列表：搜索与筛选 ----------


def seed_notes(client, db_session=None, user_id=1):
    """造 3 篇笔记：草稿「读书笔记」、草稿「旅行计划」、已发布「工作复盘」。"""
    reading = create_note(client, title="读书笔记", content="读了孙子兵法", tags="生活,随笔")
    travel = create_note(client, title="旅行计划", content="想去大理", tags="生活")
    work = create_note(client, title="工作复盘", content="本周完成了重构", tags="工作", status="published")
    if db_session is not None:
        db_session.add(Favorite(user_id=user_id, note_id=work.get_json()["data"]["id"]))
        db_session.commit()
    return reading, travel, work


def list_notes(client, **params):
    return client.get("/api/notes", query_string=params).get_json()["data"]


def test_keyword_matches_title(client):
    signup(client)
    seed_notes(client)

    data = list_notes(client, keyword="旅行")

    assert [item["title"] for item in data["items"]] == ["旅行计划"]


def test_keyword_matches_content(client):
    signup(client)
    seed_notes(client)

    data = list_notes(client, keyword="大理")

    assert [item["title"] for item in data["items"]] == ["旅行计划"]


def test_tag_filter_returns_only_matching_notes(client):
    signup(client)
    seed_notes(client)

    data = list_notes(client, tag="工作")

    assert [item["title"] for item in data["items"]] == ["工作复盘"]


def test_status_filter_returns_only_drafts(client):
    signup(client)
    seed_notes(client)

    data = list_notes(client, status="draft")

    assert sorted(item["title"] for item in data["items"]) == ["旅行计划", "读书笔记"]


def test_status_filter_returns_only_published(client):
    signup(client)
    seed_notes(client)

    data = list_notes(client, status="published")

    assert [item["title"] for item in data["items"]] == ["工作复盘"]


def test_keyword_tag_and_status_stack_together(client):
    signup(client)
    seed_notes(client)

    data = list_notes(client, keyword="重构", tag="工作", status="published")

    assert [item["title"] for item in data["items"]] == ["工作复盘"]

    empty = list_notes(client, keyword="重构", tag="工作", status="draft")
    assert empty["items"] == []


def test_list_returns_user_tags_deduped(client):
    signup(client)
    seed_notes(client)

    data = list_notes(client)

    assert sorted(data["tags"]) == sorted(["工作", "生活", "随笔"])


def test_list_only_returns_current_users_notes(client):
    owner_id = signup(client, email="owner@example.com", username="作者")
    seed_notes(client, user_id=owner_id)
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")
    create_note(client, title="别人的笔记", content="看不见", tags="秘密")

    data = list_notes(client)

    assert [item["title"] for item in data["items"]] == ["别人的笔记"]
    assert data["tags"] == ["秘密"]


def test_list_is_sorted_by_updated_at_desc(client):
    signup(client)
    seed_notes(client)
    oldest = list_notes(client)["items"][-1]["id"]
    client.put(
        f"/api/notes/{oldest}",
        json={"title": "读书笔记", "content": "读了孙子兵法", "tags": "随笔", "status": "draft"},
    )

    data = list_notes(client)

    # 刚更新的那篇应当排到最前
    assert data["items"][0]["id"] == oldest


# ---------- 工作台 ----------


def test_workspace_summary_counts_drafts_published_and_favorites(client, db_session):
    user_id = signup(client)
    seed_notes(client, db_session, user_id=user_id)

    resp = client.get("/api/workspace/summary")
    body = resp.get_json()

    assert body["code"] == Code.OK
    assert body["data"]["draft_count"] == 2
    assert body["data"]["published_count"] == 1
    assert body["data"]["favorite_count"] == 1


def test_workspace_summary_recent_is_limited_to_five_and_ordered(client, db_session):
    user_id = signup(client)
    for index in range(7):
        create_note(client, title=f"笔记{index}", content=f"正文{index}", tags="")
    db_session.commit()

    data = client.get("/api/workspace/summary").get_json()["data"]

    assert len(data["recent"]) == 5
    assert [item["title"] for item in data["recent"]] == [
        "笔记6",
        "笔记5",
        "笔记4",
        "笔记3",
        "笔记2",
    ]
    assert set(data["recent"][0]) == {"id", "title", "status", "updated_at"}


def test_workspace_summary_requires_login(client):
    assert client.get("/api/workspace/summary").get_json()["code"] == Code.UNAUTHORIZED


# ---------- 页面路由 ----------


def test_workspace_page_renders_stats_and_actions(client):
    signup(client)

    resp = client.get("/workspace")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert html.count("<h1") == 1
    for copy in ("工作台", "草稿", "已发布", "收藏", "最近文章", "新建文章", "我的文章"):
        assert copy in html


def test_notes_page_renders_filters(client):
    signup(client)

    resp = client.get("/notes")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert html.count("<h1") == 1
    for copy in ("我的文章", "标签", "状态", "全部", "草稿", "已发布", "清空筛选"):
        assert copy in html


def test_new_note_page_is_reachable(client):
    signup(client)

    resp = client.get("/notes/new")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert html.count("<h1") == 1
    assert "文章标题" in html
    assert "开始书写你的笔记" in html
    assert "保存草稿" in html
    assert "发布文章" in html
    assert "预览" in html
    assert 'href="/notes/new"' not in html  # 新建页自身不应再链到新建


def test_editor_page_loads_vendor_and_rendering(client):
    signup(client)
    html = client.get("/notes/new").get_data(as_text=True)

    assert "markdown.js" in html
    assert "marked.umd.js" in html
    assert "purify.min.js" in html
    assert "editor.js" in html


def test_detail_and_edit_pages_require_login(client):
    assert client.get("/notes/1").status_code == 302
    assert client.get("/notes/1/edit").status_code == 302
    assert client.get("/notes/new").status_code == 302


def test_detail_page_is_reachable_for_owner(client):
    signup(client)
    note_id = create_note(client).get_json()["data"]["id"]

    resp = client.get(f"/notes/{note_id}")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "返回列表" in html
    assert "编辑" in html
    assert "删除" in html


def test_detail_page_hides_other_users_note(client):
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client).get_json()["data"]["id"]
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    resp = client.get(f"/notes/{note_id}")

    assert resp.status_code == 404
    assert "内容不存在或已被删除" in resp.get_data(as_text=True)


def test_edit_page_hides_other_users_note(client):
    signup(client, email="owner@example.com", username="作者")
    note_id = create_note(client).get_json()["data"]["id"]
    client.post("/api/auth/logout", json={})
    signup(client, email="other@example.com", username="路人")

    assert client.get(f"/notes/{note_id}/edit").status_code == 404


# ---------- 时间展示 ----------


def test_note_times_are_displayed_in_local_wall_clock(client):
    """库里按 UTC 存，接口展示的必须是本地墙上时间，不能差一个时区。"""
    signup(client)
    before = datetime.now() - timedelta(minutes=1)
    note = create_note(client).get_json()["data"]
    after = datetime.now() + timedelta(minutes=1)

    shown = datetime.strptime(note["created_at"], "%Y/%m/%d %H:%M")

    assert before <= shown <= after


def test_empty_published_at_is_empty_string(client):
    signup(client)

    note = create_note(client).get_json()["data"]

    assert note["published_at"] == ""
