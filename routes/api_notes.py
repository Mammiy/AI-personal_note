"""笔记接口：增删改查、列表、版本。"""

from flask import Blueprint, request
from flask_login import current_user, login_required

from extensions import db
from models import Note
from services import note as note_service
from utils.errors import ApiError
from utils.response import Code, ok

bp = Blueprint("api_notes", __name__)


def _json_body():
    """写接口强制 application/json，阻断跨站表单提交。"""
    if "application/json" not in (request.content_type or ""):
        raise ApiError(Code.PARAM_ERROR, "请求格式不正确")

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(Code.PARAM_ERROR, "请求格式不正确")
    return data


def _own_note(note_id):
    """取笔记并校验归属：不存在或不属于当前用户一律按无权限处理。"""
    note = db.session.get(Note, note_id)
    if note is None or note.user_id != current_user.id:
        raise ApiError(Code.FORBIDDEN, "没有权限执行该操作")
    return note


@bp.get("/api/notes")
@login_required
def index():
    items = note_service.list_notes(
        current_user,
        keyword=request.args.get("keyword"),
        tag=request.args.get("tag"),
        status=request.args.get("status"),
    )
    return ok(
        {
            "items": [note_service.public_note(item) for item in items],
            "tags": note_service.user_tags(current_user),
        }
    )


@bp.post("/api/notes")
@login_required
def create():
    note = note_service.create_note(current_user, _json_body())
    return ok(note_service.public_note(note))


@bp.put("/api/notes/<int:id>")
@login_required
def update(id):
    data = _json_body()
    note = _own_note(id)
    if data.get("status") == "published":
        note = note_service.publish_note(note, data)
    else:
        note = note_service.update_note(note, data, status="draft")
    return ok(note_service.public_note(note))


@bp.get("/api/notes/<int:id>")
@login_required
def detail(id):
    note = _own_note(id)
    return ok({"note": note_service.public_note(note), "can_edit": True})


@bp.delete("/api/notes/<int:id>")
@login_required
def delete(id):
    note = _own_note(id)
    note_service.delete_note(note)
    return ok({})
