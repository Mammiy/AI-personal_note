"""AI 润色服务 F11：提示词构造、模型调用、错误映射、模拟回退、频率限制。

全程用 monkeypatch 替换 services.ai.requests.post，不发起任何真实网络请求。
"""

import pytest
import requests
from flask_login import login_user

from models import User
from services import ai as ai_service
from utils.errors import ApiError
from utils.response import Code


class FakeResponse:
    """只实现服务层用到的 status_code / json()，够用且不引额外依赖。"""

    def __init__(self, status_code=200, payload=None, bad_json=False):
        self.status_code = status_code
        self._payload = payload
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("上游返回的不是合法 JSON")
        return self._payload


def content_response(content):
    return FakeResponse(200, {"choices": [{"message": {"content": content}}]})


@pytest.fixture(autouse=True)
def reset_rate():
    ai_service._RATE.clear()
    yield
    ai_service._RATE.clear()


@pytest.fixture
def user(app, db_session):
    person = User(email="ai@example.com", username="润色用户", password_hash="x")
    db_session.add(person)
    db_session.commit()
    return person


def run(app, user, text, **overrides):
    """在登录态的请求上下文里调用服务层 polish。"""
    app.config.update(overrides)
    with app.test_request_context("/api/ai/polish"):
        login_user(user)
        return ai_service.polish(text)


# ---------- 入参边界 ----------


def test_empty_text_is_rejected(app, user):
    with pytest.raises(ApiError) as err:
        run(app, user, "", AI_API_KEY="")

    assert err.value.code == Code.PARAM_ERROR
    assert err.value.message == "请先选中要润色的文本"


def test_blank_text_is_rejected(app, user):
    with pytest.raises(ApiError) as err:
        run(app, user, "  \n\t ", AI_API_KEY="")

    assert err.value.code == Code.PARAM_ERROR
    assert err.value.message == "请先选中要润色的文本"


def test_text_over_limit_is_rejected(app, user):
    with pytest.raises(ApiError) as err:
        run(app, user, "字" * (app.config["AI_MAX_CHARS"] + 1), AI_API_KEY="")

    assert err.value.code == Code.PARAM_ERROR
    assert err.value.message == "选中内容过长，请分段润色"


def test_text_at_limit_is_accepted(app, user):
    result, simulated = run(app, user, "字" * app.config["AI_MAX_CHARS"], AI_API_KEY="")

    assert simulated is True
    assert result


# ---------- 模拟回退 ----------


def test_missing_api_key_falls_back_to_simulation(app, user):
    result, simulated = run(app, user, "然后我觉得这个非常好", AI_API_KEY="")

    assert simulated is True
    assert result
    assert result != "然后我觉得这个非常好"


def test_simulation_never_calls_upstream(app, user, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("模拟回退不应发起网络请求")

    monkeypatch.setattr(ai_service.requests, "post", boom)

    result, simulated = run(app, user, "然后我觉得这个非常好", AI_API_KEY="")

    assert simulated is True
    assert result


def test_simulation_keeps_heading_line(app, user):
    text = "# 然后我觉得这个非常好"

    result, simulated = run(app, user, text, AI_API_KEY="")

    assert simulated is True
    assert result == text


def test_simulation_keeps_code_block(app, user):
    text = "```\n但是我觉得非常多\n```"

    result, _ = run(app, user, text, AI_API_KEY="")

    assert result == text


ORDINARY_PROSE = [
    "今天天气不错，我去公园散步了。",
    "人生就像一场旅行，重要的是沿途的风景。",
    "这篇文章主要讲了作者对生活的感悟。",
    "读书使人明理，写作使人思考。",
    "我想练习写作,但是总是坚持不下来.",
]


def test_simulation_rewrites_ordinary_prose(app, user):
    """回归：模拟润色必须真的改写普通文章。

    用户报障「润色后内容仍然不变」：未配置密钥时走模拟分支，而旧规则表只有
    10 对词，绝大多数正常段落一字不改，导致「确认替换」后正文与原文完全相同。
    """
    for text in ORDINARY_PROSE:
        result, simulated = run(app, user, text, AI_API_KEY="")

        assert simulated is True
        assert result != text, f"模拟润色未改写任何内容：{text!r}"


def test_simulation_normalizes_chinese_punctuation(app, user):
    text = "我想练习写作,但是总是坚持不下来."

    result, _ = run(app, user, text, AI_API_KEY="")

    assert "，" in result and "。" in result
    assert "," not in result and result.rstrip()[-1] != "."


def test_simulation_replaces_each_source_word_once(app, user):
    """单趟改写：替换结果不会被同一趟的后续规则二次替换。"""
    result, _ = run(app, user, "这道菜不错。", AI_API_KEY="")

    assert result == "这道菜很好。"
    assert "相当好" not in result


def test_simulation_is_deterministic(app, user):
    text = "然后我觉得这个非常好，因为现在有很多问题。"

    first, _ = run(app, user, text, AI_API_KEY="")
    second, _ = run(app, user, text, AI_API_KEY="")

    assert first == second
    assert first != text


def test_simulation_keeps_markdown_links_and_images(app, user):
    text = "参考 [文档](https://example.com/a.b) 与 ![图](x.png)，我觉得不错。"

    result, _ = run(app, user, text, AI_API_KEY="")

    assert "[文档](https://example.com/a.b)" in result
    assert "![图](x.png)" in result
    assert "我认为" in result


def test_simulation_is_deterministic(app, user):
    text = "因为现在非常难，所以我其实想改。"

    first, _ = run(app, user, text, AI_API_KEY="")
    second, _ = run(app, user, text, AI_API_KEY="")

    assert first == second


# ---------- 真实模型分支 ----------


def test_successful_call_returns_content_and_posts_once(app, user, monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return content_response("润色结果")

    monkeypatch.setattr(ai_service.requests, "post", fake_post)

    result, simulated = run(
        app,
        user,
        "原文",
        AI_API_KEY="secret-key",
        AI_BASE_URL="http://ai.test/v1/",
        AI_MODEL="test-model",
        AI_TIMEOUT=7,
    )

    assert result == "润色结果"
    assert simulated is False
    assert len(calls) == 1
    assert calls[0]["url"] == "http://ai.test/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer secret-key"
    assert calls[0]["timeout"] == 7
    assert calls[0]["json"]["model"] == "test-model"
    assert calls[0]["json"]["messages"][0]["content"] == ai_service.SYSTEM_PROMPT
    assert calls[0]["json"]["messages"][1]["content"] == "原文"


def test_timeout_maps_to_ai_timeout(app, user, monkeypatch):
    def timeout_post(*args, **kwargs):
        raise requests.Timeout("upstream slow")

    monkeypatch.setattr(ai_service.requests, "post", timeout_post)

    with pytest.raises(ApiError) as err:
        run(app, user, "正文", AI_API_KEY="k", AI_BASE_URL="http://x")

    assert err.value.code == Code.AI_TIMEOUT
    assert err.value.message == "润色请求超时，请稍后重试"


def test_request_exception_maps_to_ai_error_without_stack(app, user, monkeypatch):
    def broken_post(*args, **kwargs):
        raise requests.RequestException("connect failed: key=secret-key")

    monkeypatch.setattr(ai_service.requests, "post", broken_post)

    with pytest.raises(ApiError) as err:
        run(app, user, "正文", AI_API_KEY="k", AI_BASE_URL="http://x")

    assert err.value.code == Code.AI_ERROR
    assert err.value.message == "润色失败，请稍后重试"
    assert "secret-key" not in err.value.message


def test_non_200_status_maps_to_ai_error(app, user, monkeypatch):
    monkeypatch.setattr(
        ai_service.requests, "post", lambda *a, **k: FakeResponse(500, {})
    )

    with pytest.raises(ApiError) as err:
        run(app, user, "正文", AI_API_KEY="k", AI_BASE_URL="http://x")

    assert err.value.code == Code.AI_ERROR
    assert err.value.message == "润色失败，请稍后重试"


def test_unparsable_payload_maps_to_ai_error(app, user, monkeypatch):
    monkeypatch.setattr(
        ai_service.requests, "post", lambda *a, **k: FakeResponse(200, {"odd": True})
    )

    with pytest.raises(ApiError) as err:
        run(app, user, "正文", AI_API_KEY="k", AI_BASE_URL="http://x")

    assert err.value.code == Code.AI_ERROR
    assert err.value.message == "润色失败，请稍后重试"


def test_broken_json_maps_to_ai_error(app, user, monkeypatch):
    monkeypatch.setattr(
        ai_service.requests,
        "post",
        lambda *a, **k: FakeResponse(200, None, bad_json=True),
    )

    with pytest.raises(ApiError) as err:
        run(app, user, "正文", AI_API_KEY="k", AI_BASE_URL="http://x")

    assert err.value.code == Code.AI_ERROR
    assert err.value.message == "润色失败，请稍后重试"


def test_empty_content_maps_to_no_result_message(app, user, monkeypatch):
    monkeypatch.setattr(
        ai_service.requests, "post", lambda *a, **k: content_response("")
    )

    with pytest.raises(ApiError) as err:
        run(app, user, "正文", AI_API_KEY="k", AI_BASE_URL="http://x")

    assert err.value.code == Code.AI_ERROR
    assert err.value.message == "未能生成润色结果，请调整选中内容后重试"


def test_fenced_content_is_stripped(app, user, monkeypatch):
    monkeypatch.setattr(
        ai_service.requests,
        "post",
        lambda *a, **k: content_response("```markdown\n润色后的文本\n```"),
    )

    result, simulated = run(app, user, "正文", AI_API_KEY="k", AI_BASE_URL="http://x")

    assert simulated is False
    assert result == "润色后的文本"
    assert "```" not in result


# ---------- 频率限制 ----------


def test_eleventh_request_within_one_minute_is_rejected(app, user):
    for _ in range(10):
        run(app, user, "然后我觉得这个非常好", AI_API_KEY="")

    with pytest.raises(ApiError) as err:
        run(app, user, "然后我觉得这个非常好", AI_API_KEY="")

    assert err.value.code == Code.AI_ERROR
    assert err.value.message == "润色请求过于频繁，请稍后再试"


def test_rate_limit_is_per_user(app, user, db_session):
    other = User(email="other@example.com", username="另一位", password_hash="x")
    db_session.add(other)
    db_session.commit()

    for _ in range(10):
        run(app, user, "然后我觉得这个非常好", AI_API_KEY="")

    result, simulated = run(app, other, "然后我觉得这个非常好", AI_API_KEY="")

    assert simulated is True
    assert result


def test_rate_limit_resets_after_window(app, user, monkeypatch):
    real_time = ai_service.time.time
    now = real_time()
    monkeypatch.setattr(ai_service.time, "time", lambda: now)

    for _ in range(10):
        run(app, user, "然后我觉得这个非常好", AI_API_KEY="")

    monkeypatch.setattr(ai_service.time, "time", lambda: now + 61)

    result, simulated = run(app, user, "然后我觉得这个非常好", AI_API_KEY="")

    assert simulated is True
    assert result


# ---------- 接口层 /api/ai/polish ----------


def signup(client, email="ai@example.com", username="润色用户"):
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


def test_polish_endpoint_returns_text_and_simulated_flag(client):
    signup(client)

    resp = client.post("/api/ai/polish", json={"text": "然后我觉得这个非常好"})
    body = resp.get_json()

    assert body["code"] == Code.OK
    assert set(body["data"]) == {"text", "simulated"}
    assert body["data"]["simulated"] is True
    assert body["data"]["text"]
    assert body["data"]["text"] != "然后我觉得这个非常好"


def test_polish_endpoint_rejects_blank_text(client):
    signup(client)

    resp = client.post("/api/ai/polish", json={"text": "   "})
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "请先选中要润色的文本"
    assert body["data"] is None


def test_polish_endpoint_rejects_overlong_text(client):
    signup(client)

    resp = client.post("/api/ai/polish", json={"text": "字" * 5001})
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "选中内容过长，请分段润色"


def test_polish_endpoint_requires_json_body(client):
    signup(client)

    resp = client.post("/api/ai/polish", data="text= hello")
    body = resp.get_json()

    assert body["code"] == Code.PARAM_ERROR
    assert body["message"] == "请求格式不正确"


def test_polish_endpoint_requires_login(client):
    body = client.post("/api/ai/polish", json={"text": "正文"}).get_json()

    assert body["code"] == Code.UNAUTHORIZED
    assert body["message"] == "请先登录"


def test_polish_endpoint_maps_upstream_timeout(client, app, monkeypatch):
    signup(client)
    app.config["AI_API_KEY"] = "k"
    app.config["AI_BASE_URL"] = "http://x"

    def timeout_post(*args, **kwargs):
        raise requests.Timeout("upstream slow")

    monkeypatch.setattr(ai_service.requests, "post", timeout_post)

    body = client.post("/api/ai/polish", json={"text": "正文"}).get_json()

    assert body["code"] == Code.AI_TIMEOUT
    assert body["message"] == "润色请求超时，请稍后重试"


def test_polish_endpoint_never_exposes_api_key(client, app, monkeypatch):
    signup(client)
    app.config["AI_API_KEY"] = "super-secret-key"
    app.config["AI_BASE_URL"] = "http://x"

    def broken_post(*args, **kwargs):
        raise requests.RequestException("boom super-secret-key")

    monkeypatch.setattr(ai_service.requests, "post", broken_post)

    body = client.post("/api/ai/polish", json={"text": "正文"}).get_json()

    assert body["code"] == Code.AI_ERROR
    assert "super-secret-key" not in body["message"]
