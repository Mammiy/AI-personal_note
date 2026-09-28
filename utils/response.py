"""统一响应封装：所有 /api/* 必须经 ok() / fail() 返回。"""

from flask import jsonify

# 全链路 UTF-8：JSON 响应显式声明 charset=utf-8（R3）
CONTENT_TYPE = "application/json; charset=utf-8"


def _jsonify(payload):
    resp = jsonify(payload)
    resp.headers["Content-Type"] = CONTENT_TYPE
    return resp


class Code:
    """业务码词表。语义保持稳定，实现阶段只增不改。"""

    OK = "OK"
    PARAM_ERROR = "PARAM_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    SHARE_CLOSED = "SHARE_CLOSED"
    SHARE_PASSWORD_REQUIRED = "SHARE_PASSWORD_REQUIRED"
    SHARE_PASSWORD_WRONG = "SHARE_PASSWORD_WRONG"
    AI_NOT_CONFIGURED = "AI_NOT_CONFIGURED"
    AI_TIMEOUT = "AI_TIMEOUT"
    AI_ERROR = "AI_ERROR"
    UPLOAD_TOO_LARGE = "UPLOAD_TOO_LARGE"
    UPLOAD_TYPE_ERROR = "UPLOAD_TYPE_ERROR"
    SERVER_ERROR = "SERVER_ERROR"


def ok(data=None, message="操作成功"):
    """成功响应。"""
    return _jsonify({"code": Code.OK, "message": message, "data": data})


def fail(code, message, http=200):
    """失败响应：业务错误统一 HTTP 200，前端只按 code 分支。"""
    return _jsonify({"code": code, "message": message, "data": None}), http
