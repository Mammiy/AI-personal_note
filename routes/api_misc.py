"""杂项接口：健康检查、工作台汇总、上传、AI 润色。"""

from flask import Blueprint, request
from flask_login import current_user, login_required

from services import ai as ai_service
from services import note as note_service
from services import upload as upload_service
from utils.errors import ApiError
from utils.response import Code, ok

bp = Blueprint("api_misc", __name__)


def _json_body():
    """写接口强制 application/json，阻断跨站表单提交。"""
    if "application/json" not in (request.content_type or ""):
        raise ApiError(Code.PARAM_ERROR, "请求格式不正确")

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(Code.PARAM_ERROR, "请求格式不正确")
    return data


@bp.get("/api/health")
def health():
    return ok({"status": "up"})


@bp.get("/api/workspace/summary")
@login_required
def workspace_summary():
    return ok(note_service.workspace_summary(current_user))


@bp.post("/api/upload")
@login_required
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        raise ApiError(Code.PARAM_ERROR, "请选择要上传的图片")
    return ok({"url": upload_service.save_image(file)})


@bp.post("/api/ai/polish")
@login_required
def ai_polish():
    """润色选中的一段文本：只上传选区，不上传整篇笔记。"""
    data = _json_body()
    text, simulated = ai_service.polish(data.get("text") or "")
    return ok({"text": text, "simulated": simulated})
