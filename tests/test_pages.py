"""主页与关于页的聚焦测试：HTTP 可达 + 关键中文文案 + 登录态切换。"""

FEATURES = ["简洁易用", "云端同步", "隐私保护", "灵活分类"]


def register_and_login(client, email="reader@example.com", username="读者"):
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": "secret123", "confirm": "secret123"},
    )
    assert resp.get_json()["code"] == "OK"
    return resp


def test_home_page_is_reachable_with_hero_copy(client):
    resp = client.get("/")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "记录生活 · 书写成长" in html
    assert "遇见美好" in html
    assert html.count("<h1") == 1
    assert "charset=utf-8" in resp.headers["Content-Type"]


def test_home_page_shows_guest_nav_and_buttons(client):
    html = client.get("/").get_data(as_text=True)

    assert 'href="/login"' in html
    assert 'href="/register"' in html
    assert "我的文章" not in html
    assert "开始记录" in html
    assert 'href="/register"' in html
    assert "了解更多" in html
    assert 'href="/about"' in html


def test_home_page_lists_four_features(client):
    html = client.get("/").get_data(as_text=True)

    for name in FEATURES:
        assert name in html


def test_about_page_is_reachable(client):
    resp = client.get("/about")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "关于个人笔记" in html
    assert html.count("<h1") == 1
    assert "技术栈" in html


def test_home_page_switches_to_authed_state(client):
    register_and_login(client)
    html = client.get("/").get_data(as_text=True)

    assert "我的文章" in html
    assert "个人主页" in html
    assert "退出" in html
    assert "进入工作台" in html
    assert 'href="/workspace"' in html
    assert "开始记录" not in html


def test_guest_visiting_workspace_is_redirected_to_login(client):
    resp = client.get("/workspace")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_unknown_page_returns_404_page(client):
    resp = client.get("/definitely-not-here")

    assert resp.status_code == 404
    assert "内容不存在或已被删除" in resp.get_data(as_text=True)
