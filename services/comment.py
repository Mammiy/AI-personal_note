"""评论业务规则：发布、列表、开关与删除权限判定。

删除权限只在这里判定：笔记作者可删任意评论，登录用户可删自己的评论，访客一律不可删。
"""

from extensions import db
from models import Comment, Note, User
from services import note as note_service
from utils.errors import ApiError
from utils.response import Code

MIN_GUEST_NAME = 1
MAX_GUEST_NAME = 20


def can_delete(comment, viewer, note=None):
    """作者 > 本人在登录态下删自己的 > 其余（含访客）一律不可删。"""
    if viewer is None or not getattr(viewer, "is_authenticated", False):
        return False
    if note is not None and note.user_id == viewer.id:
        return True
    return comment.user_id is not None and comment.user_id == viewer.id


def _usernames(rows):
    """一次性取出评论涉及的用户名，避免逐条查询。"""
    ids = {row.user_id for row in rows if row.user_id}
    if not ids:
        return {}
    users = User.query.filter(User.id.in_(ids)).all()
    return {user.id: user.username for user in users}


def public_comment(comment, viewer=None, note=None, names=None):
    """单条评论对外结构：来源用 is_guest 区分，展示名取用户名或访客昵称。"""
    display_name = comment.guest_name or ""
    if comment.user_id is not None:
        display_name = (names or {}).get(comment.user_id)
        if display_name is None:
            # 单条查询场景（如创建后回显）也要给出用户名，不能留空
            user = db.session.get(User, comment.user_id)
            display_name = user.username if user else ""

    return {
        "id": comment.id,
        "display_name": display_name,
        "is_guest": comment.user_id is None,
        "content": comment.content,
        "created_at": note_service.format_time(comment.created_at),
        "can_delete": can_delete(comment, viewer, note),
    }


def list_comments(note, viewer=None):
    """评论开关关闭时列表为空（历史评论不对外展示），按时间正序返回。"""
    if not note.allow_comments:
        return {"items": [], "enabled": False}

    rows = (
        Comment.query.filter_by(note_id=note.id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
        .all()
    )
    names = _usernames(rows)
    return {
        "items": [public_comment(row, viewer, note, names) for row in rows],
        "enabled": True,
    }


def set_enabled(note, enabled):
    """作者开关评论区。"""
    note.allow_comments = bool(enabled)
    db.session.commit()
    return note


def add_comment(note, content, user=None, guest_name=None):
    """登录用户带 user，分享访客带 guest_name；昵称与内容都在此校验。"""
    content = (content or "").strip()
    if not content:
        raise ApiError(Code.PARAM_ERROR, "请输入评论内容")

    name = None
    if user is None:
        name = (guest_name or "").strip()
        if not (MIN_GUEST_NAME <= len(name) <= MAX_GUEST_NAME):
            raise ApiError(Code.PARAM_ERROR, "请填写 1 到 20 个字符的昵称")

    if not note.allow_comments:
        raise ApiError(Code.FORBIDDEN, "评论已关闭")

    comment = Comment(
        note_id=note.id,
        user_id=user.id if user is not None else None,
        guest_name=name,
        content=content,
    )
    db.session.add(comment)
    db.session.commit()
    return comment


def delete_comment(comment, viewer, note=None):
    """权限不足与评论不存在都按无权限处理，不泄露资源是否存在。"""
    if comment is None or not can_delete(comment, viewer, note):
        raise ApiError(Code.FORBIDDEN, "没有权限执行该操作")

    db.session.delete(comment)
    db.session.commit()


def own_note_of(comment):
    """评论所属笔记，供权限判定使用。"""
    if comment is None:
        return None
    return db.session.get(Note, comment.note_id)
