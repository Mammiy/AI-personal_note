"""账号接口：注册 / 登录 / 退出 / 当前用户。"""

from flask import Blueprint, redirect, request, url_for
from flask_login import current_user, login_required

from extensions import login_manager
from services import auth as auth_service
from utils.errors import ApiError
from utils.response import Code, fail, ok

bp = Blueprint("api_auth", __name__)


def _json_body():
    """写接口强制 application/json，阻断跨站表单提交。"""
    if "application/json" not in (request.content_type or ""):
        raise ApiError(Code.PARAM_ERROR, "请求格式不正确")

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(Code.PARAM_ERROR, "请填写邮箱")
    return data


@bp.post("/api/auth/register")
def register():
    data = _json_body()
    user = auth_service.register(
        data.get("email"),
        data.get("username"),
        data.get("password"),
        data.get("confirm"),
    )
    return ok(auth_service.public_user(user))


@bp.post("/api/auth/login")
def login():
    data = _json_body()
    user = auth_service.login(data.get("email"), data.get("password"))
    return ok(auth_service.public_user(user))


@bp.post("/api/auth/logout")
@login_required
def logout():
    auth_service.logout()
    return ok({"logged_out": True})


@bp.get("/api/auth/me")
@login_required
def me():
    return ok(auth_service.public_user(current_user))


@login_manager.unauthorized_handler
def unauthorized():
    """API 返回未授权 JSON，页面跳转登录页。"""
    if request.path.startswith("/api/"):
        return fail(Code.UNAUTHORIZED, "请先登录")
    return redirect(url_for("pages.login"))
