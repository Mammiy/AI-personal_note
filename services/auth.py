"""账号业务规则：注册校验、密码哈希、登录与会话。"""

import re

from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User
from utils.errors import ApiError
from utils.response import Code

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_register(email, username, password, confirm):
    """注册字段校验，任一不满足抛 ApiError(PARAM_ERROR, 中文文案)。"""
    email = (email or "").strip()
    username = (username or "").strip()
    password = password or ""
    confirm = confirm or ""

    if not email:
        raise ApiError(Code.PARAM_ERROR, "请填写邮箱")
    if not EMAIL_RE.match(email):
        raise ApiError(Code.PARAM_ERROR, "邮箱格式不正确")
    if not username:
        raise ApiError(Code.PARAM_ERROR, "请填写用户名")
    if not 2 <= len(username) <= 20:
        raise ApiError(Code.PARAM_ERROR, "用户名需为 2 至 20 个字符")
    if not password:
        raise ApiError(Code.PARAM_ERROR, "请填写密码")
    if len(password) < 6:
        raise ApiError(Code.PARAM_ERROR, "密码至少需要 6 位")
    if password != confirm:
        raise ApiError(Code.PARAM_ERROR, "两次输入的密码不一致")

    return email, username, password


def register(email, username, password, confirm):
    """注册并自动登录；邮箱/用户名唯一性在此判定。"""
    email, username, password = validate_register(email, username, password, confirm)

    if User.query.filter_by(email=email).first():
        raise ApiError(Code.CONFLICT, "该邮箱已被注册")
    if User.query.filter_by(username=username).first():
        raise ApiError(Code.CONFLICT, "该用户名已被使用")

    user = User(
        email=email,
        username=username,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return user


def login(email, password):
    """登录失败统一提示「邮箱或密码错误」，不泄露账号是否存在。"""
    email = (email or "").strip()
    user = User.query.filter_by(email=email).first() if email else None

    if not user or not check_password_hash(user.password_hash, password or ""):
        raise ApiError(Code.PARAM_ERROR, "邮箱或密码错误")

    login_user(user)
    return user


def logout():
    """清空会话。"""
    logout_user()


def public_user(user):
    """对外返回的用户信息，不含任何密码字段。"""
    return {"id": user.id, "email": user.email, "username": user.username}
