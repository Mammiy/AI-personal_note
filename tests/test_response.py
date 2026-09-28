"""统一响应封装与全局错误处理的聚焦测试。"""

from flask import request

from extensions import db
from utils.errors import ApiError
from utils.response import Code, fail, ok


def test_ok_envelope_and_utf8(app):
    with app.test_request_context():
        resp = ok({"status": "up"})

    assert resp.status_code == 200
    assert "charset=utf-8" in resp.headers["Content-Type"]

    body = resp.get_json()
    assert set(body.keys()) == {"code", "message", "data"}
    assert body["code"] == "OK"
    assert body["message"] == "操作成功"
    assert body["data"] == {"status": "up"}
    # 中文不得被转义为 \uXXXX
    assert "操作成功" in resp.get_data(as_text=True)


def test_fail_envelope_uses_http_200_and_null_data(app):
    with app.test_request_context():
        resp, status = fail(Code.PARAM_ERROR, "请填写邮箱")

    assert status == 200
    assert resp.get_json() == {
        "code": "PARAM_ERROR",
        "message": "请填写邮箱",
        "data": None,
    }


def test_health_endpoint(client):
    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert "charset=utf-8" in resp.headers["Content-Type"]
    assert resp.get_json() == {
        "code": "OK",
        "message": "操作成功",
        "data": {"status": "up"},
    }


def test_api_error_becomes_envelope(app, client):
    @app.get("/api/_api_error")
    def raise_api_error():
        raise ApiError(Code.NOT_FOUND, "内容不存在或已被删除")

    resp = client.get("/api/_api_error")

    assert resp.get_json() == {
        "code": "NOT_FOUND",
        "message": "内容不存在或已被删除",
        "data": None,
    }


def test_unexpected_exception_hides_internal_detail(app, client):
    @app.get("/api/_boom")
    def boom():
        raise RuntimeError("内部堆栈 secret-detail")

    resp = client.get("/api/_boom")
    body = resp.get_json()

    assert body["code"] == "SERVER_ERROR"
    assert body["message"] == "服务器繁忙，请稍后重试"
    assert body["data"] is None

    text = resp.get_data(as_text=True)
    assert "secret-detail" not in text
    assert "Traceback" not in text


def test_unknown_api_path_returns_not_found(client):
    resp = client.get("/api/definitely-not-here")

    assert resp.get_json()["code"] == "NOT_FOUND"
    assert resp.get_json()["message"] == "内容不存在或已被删除"


def test_upload_over_limit_returns_chinese_message(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 64

    @app.post("/api/_post_target")
    def post_target():
        request.get_data()  # 读取请求体，触发体积上限校验
        return ok({"received": True})

    resp = client.post(
        "/api/_post_target", data="x" * 200, content_type="application/json"
    )

    assert resp.get_json()["code"] == "UPLOAD_TOO_LARGE"
    assert resp.get_json()["message"] == "图片大小不能超过 5MB"


def test_all_tables_are_created(app):
    with app.app_context():
        names = set(db.metadata.tables.keys())

    assert {"user", "note", "note_version", "comment", "favorite"} <= names
