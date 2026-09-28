"""收藏业务规则：切换幂等、列表按收藏时间倒序。

不做任何「不能收藏自己的笔记」之类的限制，用户 × 笔记 唯一由表约束保证。
"""

from extensions import db
from models import Favorite, Note
from services import note as note_service


def can_view(user, note):
    """可见范围：自己的笔记，或仍处于开启状态的分享笔记。

    收藏列表会展示笔记标题，因此不能让用户凭 id 收藏他人未分享的笔记。
    """
    if note is None:
        return False
    return note.user_id == user.id or note.is_shared


def is_favorited(user, note):
    """当前用户是否已收藏该笔记。"""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return (
        Favorite.query.filter_by(user_id=user.id, note_id=note.id).first() is not None
    )


def toggle(user, note, on):
    """收藏与取消都幂等：重复收藏只保留一条，重复取消不报错。"""
    row = Favorite.query.filter_by(user_id=user.id, note_id=note.id).first()

    if on:
        if row is None:
            db.session.add(Favorite(user_id=user.id, note_id=note.id))
            db.session.commit()
        return True

    if row is not None:
        db.session.delete(row)
        db.session.commit()
    return False


def list_favorites(user):
    """按收藏时间倒序返回，同秒以收藏 id 倒序兜底保证稳定。"""
    rows = (
        Favorite.query.filter_by(user_id=user.id)
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
        .all()
    )

    items = []
    for row in rows:
        note = db.session.get(Note, row.note_id)
        # 笔记被删除，或别人的分享已关闭，都不再出现在收藏列表里
        if note is None or not can_view(user, note):
            continue
        items.append(
            {
                "note_id": note.id,
                "title": note.title,
                "status": note.status,
                "updated_at": note_service.format_time(note.updated_at),
                "favorited_at": note_service.format_time(row.created_at),
            }
        )
    return {"items": items}
