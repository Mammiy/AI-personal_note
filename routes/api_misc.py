"""杂项接口：健康检查、工作台汇总、上传、AI 润色。"""

from flask import Blueprint, request
from flask_login import current_user, login_required

from services import note as note_service
from services import upload as upload_service
from utils.errors import ApiError
from utils.response import Code, ok

bp = Blueprint("api_misc", __name__)


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
