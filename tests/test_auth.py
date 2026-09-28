"""注册 / 登录 / 退出闭环与账号校验的聚焦测试。"""

from models import User
from utils.response import Code


def payload(email="reader@example.com", username="读书人", password="secret123", **extra):
    data = {
        "email": email,
        "username": username,
        "password": password,
        "confirm": password,
    }
    data.update(extra)
    return data


# ---------- 注册 ----------


def test_register_success_and_auto_login(client, db_session):
    resp = client.post("/api/auth/register", json=payload())

    assert resp.get_json()["code"] == Code.OK
    assert resp.get_json()["data"]["username"] == "读书人"

    user = db_session.query(User).filter_by(email="reader@example.com").one()
    assert user.password_hash != "secret123"
    assert len(user.password_hash) > 20

    me = client.get("/api/auth/me")
    assert me.get_json()["data"]["id"] == user.id


def test_register_rejects_duplicate_email(client):
    client.post("/api/auth/register", json=payload())

    resp = client.post("/api/auth/register", json=payload(username="另一个人"))
    body = resp.get_json()

    assert body["code"] == Code.CONFLICT
    assert body["message"] == "该邮箱已被注册"


def test_register_rejects_duplicate_username(client):
    client.post("/api/auth/register", json=payload())

    resp = client.post("/api/auth/register", json=payload(email="other@example.com"))
    body = resp.get_json()

    assert body["code"] == Code.CONFLICT
    assert body["message"] == "该用户名已被使用"


def test_register_rejects_mismatched_password(client):
    resp = client.post("/api/auth/register", json=payload(confirm="different1"))
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "两次输入的密码不一致"


def test_register_rejects_short_password(client):
    resp = client.post("/api/auth/register", json=payload(password="12345"))
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert "密码" in body["message"]


def test_register_rejects_bad_email(client):
    resp = client.post("/api/auth/register", json=payload(email="not-an-email"))
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "邮箱格式不正确"


def test_register_requires_username_length(client):
    resp = client.post("/api/auth/register", json=payload(username="我"))
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert "用户名" in body["message"]


def test_register_requires_email(client):
    resp = client.post("/api/auth/register", json=payload(email=""))
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "请填写邮箱"


def test_register_with_empty_json_body_is_rejected(client):
    resp = client.post(
        "/api/auth/register", data="null", content_type="application/json"
    )
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "请填写邮箱"


# ---------- 登录 ----------


def test_login_wrong_password_uses_uniform_message(client):
    client.post("/api/auth/register", json=payload())

    resp = client.post(
        "/api/auth/login", json={"email": "reader@example.com", "password": "wrong-pass"}
    )
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "邮箱或密码错误"


def test_login_unknown_account_uses_same_message(client):
    resp = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever1"}
    )
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "邮箱或密码错误"


def test_login_success_returns_user(client):
    client.post("/api/auth/register", json=payload())
    client.post("/api/auth/logout", json={})

    resp = client.post(
        "/api/auth/login", json={"email": "reader@example.com", "password": "secret123"}
    )

    assert resp.get_json()["code"] == Code.OK
    assert resp.get_json()["data"]["email"] == "reader@example.com"


def test_form_encoded_write_request_is_rejected(client):
    resp = client.post(
        "/api/auth/login",
        data="email=a@b.com&password=x",
        content_type="application/x-www-form-urlencoded",
    )
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "请求格式不正确"


# ---------- 退出与未授权 ----------


def test_protected_api_without_login_returns_unauthorized(client):
    resp = client.get("/api/auth/me")
    body = resp.get_json()

    assert body["code"] == Code.UNAUTHORIZED
    assert body["message"] == "请先登录"
    assert body["data"] is None


def test_logout_clears_session(client):
    client.post("/api/auth/register", json=payload())
    assert client.get("/api/auth/me").get_json()["code"] == Code.OK

    resp = client.post("/api/auth/logout", json={})
    assert resp.get_json()["code"] == Code.OK
    assert client.get("/api/auth/me").get_json()["code"] == Code.UNAUTHORIZED


def test_authed_user_visiting_login_is_redirected(client):
    client.post("/api/auth/register", json=payload())

    resp = client.get("/login")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/workspace")


def test_register_page_is_reachable_for_guest(client):
    resp = client.get("/register")

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "确认密码" in html
    assert html.count("<h1") == 1
