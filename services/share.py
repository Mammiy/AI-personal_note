"""分享业务规则：开关、令牌、密码哈希与校验。

约定：关闭分享后对外一律 SHARE_CLOSED，密码只存哈希、永不回传。
"""

import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import Note
from utils.errors import ApiError
from utils.response import Code

SESSION_KEY = "share_passed"


def ensure_token(note):
    """令牌为空时生成不可预测随机串（32 字符）并落库。"""
    if not note.share_token:
        note.share_token = secrets.token_hex(16)
        db.session.commit()
    return note.share_token


def set_share(note, is_shared):
    """开启时确保令牌存在；关闭时保留令牌，重新开启后链接不变。"""
    if is_shared:
        ensure_token(note)
        note.is_shared = True
    else:
        note.is_shared = False
    db.session.commit()
    return note


def set_password(note, password):
    """空字符串表示移除密码，其余写入哈希；原文不落库。"""
    if password:
        note.share_password_hash = generate_password_hash(password)
    else:
        note.share_password_hash = None
    db.session.commit()
    return note


def share_url(note):
    """分享页相对路径；详情页展示时再拼 host 得到完整链接。"""
    return f"/s/{note.share_token}"


def resolve(token):
    """按令牌取笔记；不存在或已关闭分享一律视为分享已关闭。"""
    note = Note.query.filter_by(share_token=token).one_or_none()
    if note is None or not note.is_shared:
        raise ApiError(Code.SHARE_CLOSED, "分享已关闭")
    return note


def needs_password(note, session):
    """未设密码直接放行；已设密码则看会话里是否已有该令牌的通过记录。"""
    if not note.share_password_hash:
        return False
    return note.share_token not in session.get(SESSION_KEY, [])


def mark_passed(session, token):
    """把令牌写入服务端会话，验证状态不放 URL 与前端存储。"""
    passed = list(session.get(SESSION_KEY, []))
    if token not in passed:
        passed.append(token)
    session[SESSION_KEY] = passed
    session.modified = True


def verify_password(note, password):
    """密码不匹配抛业务异常，由全局 handler 转 fail()。"""
    if not check_password_hash(note.share_password_hash or "", password or ""):
        raise ApiError(Code.SHARE_PASSWORD_WRONG, "密码错误，请重新输入")
