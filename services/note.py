"""笔记业务规则：标签解析、校验、增删改、版本快照、搜索筛选。

约定：权限判定与状态流转只发生在这里，路由层只做参数提取与响应封装。"""

from datetime import datetime, timezone

from sqlalchemy import or_

from extensions import db
from models import Comment, Favorite, Note, NoteVersion
from utils.errors import ApiError
from utils.response import Code

MAX_TITLE_LEN = 100
MAX_TAGS = 5
MAX_TAG_LEN = 12


def normalize_tags(raw):
    """标签归一化：中英文逗号切分 → 去空白 → 去重 → 最多 5 个 → 每个截断至 12 字。"""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        parts = [str(item) for item in raw]
    else:
        parts = str(raw).replace("，", ",").split(",")

    tags = []
    for part in parts:
        tag = part.strip()[:MAX_TAG_LEN]
        if not tag or tag in tags:
            continue
        tags.append(tag)
        if len(tags) >= MAX_TAGS:
            break
    return tags


def to_tags_field(tags):
    """标签列表回写为英文逗号连接的存储格式。"""
    return ",".join(tags or [])


def validate(title, tags_raw=None):
    """标题必填且不超 100 字；正文不做必填限制；标签只归一化不拒绝。"""
    title = (title or "").strip()
    if not title:
        raise ApiError(Code.PARAM_ERROR, "请填写标题")
    if len(title) > MAX_TITLE_LEN:
        raise ApiError(Code.PARAM_ERROR, "标题不能超过 100 字")
    return title, normalize_tags(tags_raw)


def format_time(value):
    """统一时间文案：2026/6/17 14:33（月日不补零，与界面契约一致）。

    库里存的是 UTC 朴素时间，展示前统一换算成本地时区，避免相差一整个时区。
    """
    if not value:
        return ""
    local = value.replace(tzinfo=timezone.utc).astimezone()
    return f"{local.year}/{local.month}/{local.day} {local.hour:02d}:{local.minute:02d}"


def public_note(note):
    """对外返回的笔记数据，标签以数组形式给出。"""
    return {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "tags": normalize_tags(note.tags),
        "status": note.status,
        "created_at": format_time(note.created_at),
        "updated_at": format_time(note.updated_at),
        "published_at": format_time(note.published_at),
    }


def _apply_status(note, status):
    """按目标状态更新主体；首次发布写 published_at，再次保存不覆盖。"""
    if status == "published":
        note.status = "published"
        if note.published_at is None:
            note.published_at = datetime.utcnow()
    elif status == "draft":
        note.status = "draft"


def create_note(user, data):
    """新建笔记：不产生版本记录。"""
    title, tags = validate(data.get("title"), data.get("tags"))
    note = Note(
        user_id=user.id,
        title=title,
        content=data.get("content") or "",
        tags=to_tags_field(tags),
        status="draft",
    )
    _apply_status(note, data.get("status"))
    db.session.add(note)
    db.session.commit()
    return note


def update_note(note, data, status=None):
    """更新笔记：先写更新前的版本快照，再更新主体，两步在同一事务内提交。"""
    title, tags = validate(data.get("title"), data.get("tags"))

    db.session.add(
        NoteVersion(
            note_id=note.id,
            title=note.title,
            content=note.content,
            tags=note.tags,
        )
    )
    note.title = title
    note.content = data.get("content") or ""
    note.tags = to_tags_field(tags)
    note.updated_at = datetime.utcnow()
    if status is not None:
        _apply_status(note, status)
    db.session.commit()
    return note


def publish_note(note, data):
    """发布：状态置为已发布，首次发布记录发布时间。"""
    return update_note(note, data, status="published")


def _ordered(query):
    """列表统一按更新时间倒序，同秒时以 id 倒序兜底，保证顺序稳定。"""
    return query.order_by(Note.updated_at.desc(), Note.id.desc())


def list_notes(user, keyword=None, tag=None, status=None):
    """按关键词、标签、状态筛选当前用户笔记，按更新时间倒序。"""
    query = Note.query.filter_by(user_id=user.id)

    keyword = (keyword or "").strip()
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(Note.title.like(like), Note.content.like(like)))

    if status in ("draft", "published"):
        query = query.filter(Note.status == status)

    notes = _ordered(query).all()

    tag = (tag or "").strip()
    if tag:
        notes = [item for item in notes if tag in normalize_tags(item.tags)]

    return notes


def user_tags(user):
    """当前用户全部笔记标签，去重后返回。"""
    tags = []
    rows = db.session.query(Note.tags).filter(
        Note.user_id == user.id, Note.tags != ""
    )
    for (field,) in rows:
        for tag in normalize_tags(field):
            if tag not in tags:
                tags.append(tag)
    return tags


def workspace_summary(user):
    """工作台统计：草稿数、已发布数、收藏数与最近 5 篇。"""
    notes = Note.query.filter_by(user_id=user.id)
    recent = _ordered(notes).limit(5).all()

    return {
        "draft_count": notes.filter_by(status="draft").count(),
        "published_count": notes.filter_by(status="published").count(),
        "favorite_count": Favorite.query.filter_by(user_id=user.id).count(),
        "recent": [
            {
                "id": item.id,
                "title": item.title,
                "status": item.status,
                "updated_at": format_time(item.updated_at),
            }
            for item in recent
        ],
    }


def delete_note(note):
    """删除笔记，连同评论、收藏、版本快照一并清空。"""
    Comment.query.filter_by(note_id=note.id).delete()
    Favorite.query.filter_by(note_id=note.id).delete()
    NoteVersion.query.filter_by(note_id=note.id).delete()
    db.session.delete(note)
    db.session.commit()
