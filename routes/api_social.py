"""社交接口：分享、评论、收藏、个人主页。

路由层只做参数提取与响应封装，业务规则与权限判定一律交给 services/。
"""

from flask import Blueprint, request, session
from flask_login import current_user, login_required

from extensions import db
from models import Comment, Note
from services import comment as comment_service
from services import favorite as favorite_service
from services import note as note_service
from services import share as share_service
from utils.errors import ApiError
from utils.response import Code, ok

bp = Blueprint("api_social", __name__)


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


@bp.put("/api/notes/<int:id>/share")
@login_required
def update_share(id):
    """分享设置：is_shared 控制开关，password 缺省不改、显式空串移除。"""
    data = _json_body()
    note = _own_note(id)

    share_service.set_share(note, bool(data.get("is_shared")))
    if "password" in data:
        share_service.set_password(note, (data.get("password") or "").strip())

    return ok(
        {
            "is_shared": note.is_shared,
            "share_url": share_service.share_url(note),
            "has_password": bool(note.share_password_hash),
        }
    )


def _share_note(token):
    """分享侧取笔记：关闭一律 SHARE_CLOSED，未通过密码验证不放行任何内容。"""
    note = share_service.resolve(token)
    if share_service.needs_password(note, session):
        raise ApiError(Code.SHARE_PASSWORD_REQUIRED, "该笔记需要密码才能查看")
    return note


@bp.get("/api/share/<token>")
def share_detail(token):
    """访客阅读：未通过密码验证前不返回任何笔记内容。"""
    note = _share_note(token)

    return ok(
        {
            "title": note.title,
            "content": note.content,
            "updated_at": note_service.format_time(note.updated_at),
            "allow_comments": note.allow_comments,
        }
    )


@bp.post("/api/share/<token>/verify")
def share_verify(token):
    """密码验证：通过状态写进服务端会话，不落 URL 与前端存储。"""
    data = _json_body()
    note = share_service.resolve(token)
    share_service.verify_password(note, data.get("password"))
    share_service.mark_passed(session, note.share_token)
    return ok({})


def _visible_note(note_id):
    """收藏可见范围：自己的笔记或已分享的笔记，其余一律无权限。"""
    note = db.session.get(Note, note_id)
    if not favorite_service.can_view(current_user, note):
        raise ApiError(Code.FORBIDDEN, "没有权限执行该操作")
    return note


# ---------- 评论 ----------


@bp.get("/api/notes/<int:id>/comments")
@login_required
def note_comments(id):
    note = _own_note(id)
    return ok(comment_service.list_comments(note, current_user))


@bp.post("/api/notes/<int:id>/comments")
@login_required
def create_note_comment(id):
    data = _json_body()
    note = _own_note(id)
    comment = comment_service.add_comment(note, data.get("content"), user=current_user)
    return ok(comment_service.public_comment(comment, current_user, note))


@bp.put("/api/notes/<int:id>/comments/enabled")
@login_required
def toggle_note_comments(id):
    data = _json_body()
    note = _own_note(id)
    comment_service.set_enabled(note, bool(data.get("enabled")))
    return ok({"enabled": note.allow_comments})


@bp.delete("/api/comments/<int:id>")
@login_required
def delete_comment(id):
    """删除权限由 service 统一判定，接口层不重复实现。"""
    comment = db.session.get(Comment, id)
    note = comment_service.own_note_of(comment)
    comment_service.delete_comment(comment, current_user, note)
    return ok({})


@bp.get("/api/share/<token>/comments")
def share_comments(token):
    note = _share_note(token)
    return ok(comment_service.list_comments(note, None))


@bp.post("/api/share/<token>/comments")
def create_share_comment(token):
    data = _json_body()
    note = _share_note(token)
    comment = comment_service.add_comment(
        note, data.get("content"), guest_name=data.get("guest_name")
    )
    return ok(comment_service.public_comment(comment, None, note))


# ---------- 收藏 ----------


@bp.post("/api/notes/<int:id>/favorite")
@login_required
def add_favorite(id):
    _json_body()
    note = _visible_note(id)
    favorite_service.toggle(current_user, note, True)
    return ok({"is_favorited": True})


@bp.delete("/api/notes/<int:id>/favorite")
@login_required
def remove_favorite(id):
    note = _visible_note(id)
    favorite_service.toggle(current_user, note, False)
    return ok({"is_favorited": False})


@bp.get("/api/favorites")
@login_required
def favorites():
    return ok(favorite_service.list_favorites(current_user))


# ---------- 个人主页 ----------


@bp.get("/api/profile")
@login_required
def profile():
    """个人信息只读 + 我的收藏 + 笔记历史入口所需的笔记清单。"""
    notes = (
        Note.query.filter_by(user_id=current_user.id)
        .order_by(Note.updated_at.desc(), Note.id.desc())
        .all()
    )
    return ok(
        {
            "user": {
                "username": current_user.username,
                "email": current_user.email,
                "created_at": note_service.format_time(current_user.created_at),
            },
            "favorites": favorite_service.list_favorites(current_user)["items"],
            "notes": [{"id": item.id, "title": item.title} for item in notes],
        }
    )
