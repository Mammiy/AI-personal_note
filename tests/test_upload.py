"""图片上传：类型白名单、随机文件名、大小限制、写盘失败。"""

import io
import re

from utils.response import Code

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


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


def upload(client, filename="photo.png", content=PNG_BYTES):
    return client.post(
        "/api/upload",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def test_allowed_image_returns_static_url(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    signup(client)

    resp = upload(client)
    body = resp.get_json()

    assert body["code"] == Code.OK
    assert re.fullmatch(r"/static/uploads/[0-9a-f]{32}\.png", body["data"]["url"]), body


def test_saved_file_lands_in_upload_folder(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    signup(client)

    url = upload(client).get_json()["data"]["url"]
    name = url.rsplit("/", 1)[-1]

    assert (tmp_path / name).exists()
    assert (tmp_path / name).read_bytes() == PNG_BYTES


def test_filename_is_randomized_not_original(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    signup(client)

    first = upload(client, filename="photo.png").get_json()["data"]["url"]
    second = upload(client, filename="photo.png").get_json()["data"]["url"]

    assert first != second
    assert "photo" not in first


def test_traversal_filename_cannot_escape_folder(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    signup(client)

    resp = upload(client, filename="../../evil.png")
    body = resp.get_json()

    assert body["code"] == Code.OK
    assert re.fullmatch(r"/static/uploads/[0-9a-f]{32}\.png", body["data"]["url"])
    assert len(list(tmp_path.iterdir())) == 1


def test_disallowed_extension_is_rejected(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    signup(client)

    resp = upload(client, filename="malware.exe", content=b"MZ")
    body = resp.get_json()

    assert body["code"] == Code.UPLOAD_TYPE_ERROR
    assert body["message"] == "仅支持 png、jpg、jpeg、webp、gif 格式的图片"
    assert list(tmp_path.iterdir()) == []


def test_missing_file_is_rejected(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    signup(client)

    resp = client.post("/api/upload", data={}, content_type="multipart/form-data")
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "请选择要上传的图片"


def test_upload_requires_login(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    resp = upload(client)

    assert resp.get_json()["code"] == Code.UNAUTHORIZED


def test_oversized_image_returns_chinese_message(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    signup(client)
    # 先登录再收紧体积限制，否则注册请求本身也会被拒
    app.config["MAX_CONTENT_LENGTH"] = 64

    resp = upload(client, content=b"x" * 512)
    body = resp.get_json()

    assert body["code"] == Code.UPLOAD_TOO_LARGE
    assert body["message"] == "图片大小不能超过 5MB"


def test_write_failure_returns_server_error(client, app, tmp_path):
    # 上传目录的父路径是一个文件，建目录必然失败
    blocker = tmp_path / "blocker"
    blocker.write_text("not-a-dir", encoding="utf-8")
    app.config["UPLOAD_FOLDER"] = str(blocker / "sub")
    signup(client)

    resp = upload(client)
    body = resp.get_json()

    assert body["code"] == Code.SERVER_ERROR
    assert body["message"] == "图片上传失败，请稍后重试"


def test_all_five_allowed_extensions_pass(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    signup(client)

    for ext in ("png", "jpg", "jpeg", "webp", "gif"):
        resp = upload(client, filename=f"pic.{ext}")

        assert resp.get_json()["code"] == Code.OK
        assert resp.get_json()["data"]["url"].endswith("." + ext)
