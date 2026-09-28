"""页面路由：只输出 HTML 骨架，不做业务判断。"""

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from extensions import db
from models import Note

bp = Blueprint("pages", __name__)


def _visible_note_or_none(note_id):
    """只返回属于当前用户的笔记，取不到一律按不存在处理。"""
    note = db.session.get(Note, note_id)
    if note is None or note.user_id != current_user.id:
        return None
    return note


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/about")
def about():
    return render_template("about.html")


@bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.workspace"))
    return render_template("login.html")


@bp.get("/register")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.workspace"))
    return render_template("register.html")


@bp.get("/workspace")
@login_required
def workspace():
    """工作台：统计卡与最近文章由 workspace.js 拉取渲染。"""
    return render_template("workspace.html")


@bp.get("/notes")
@login_required
def notes():
    """我的文章：列表与筛选由 notes.js 完成。"""
    return render_template("notes.html")


@bp.get("/notes/new")
@login_required
def note_new():
    return render_template("note_edit.html", note_id=None)


@bp.get("/notes/<int:id>")
@login_required
def note_detail(id):
    note = _visible_note_or_none(id)
    if note is None:
        return render_template("404.html"), 404
    return render_template("note_detail.html", note_id=id)


@bp.get("/notes/<int:id>/edit")
@login_required
def note_edit(id):
    note = _visible_note_or_none(id)
    if note is None:
        return render_template("404.html"), 404
    return render_template("note_edit.html", note_id=id)


@bp.get("/profile")
@login_required
def profile():
    """个人主页：三区块内容由 profile.js 拉取渲染。"""
    return render_template("profile.html")


@bp.get("/s/<token>")
def share(token):
    """分享页：只给骨架，笔记内容一律由 share.js 拉接口后再渲染。"""
    return render_template("share.html", token=token)
