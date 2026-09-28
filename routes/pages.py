"""页面路由：只输出 HTML 骨架，不做业务判断。"""

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

bp = Blueprint("pages", __name__)


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
    """工作台占位页，Phase 2 替换。"""
    return render_template("workspace.html")
