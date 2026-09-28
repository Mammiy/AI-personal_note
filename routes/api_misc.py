"""杂项接口：健康检查、工作台汇总、上传、AI 润色。"""

from flask import Blueprint

from utils.response import ok

bp = Blueprint("api_misc", __name__)


@bp.get("/api/health")
def health():
    return ok({"status": "up"})
