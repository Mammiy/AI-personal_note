"""应用工厂：配置、扩展、错误响应、蓝图注册、首次启动建表。"""

import os

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException

from config import Config
from extensions import db, login_manager
from models import User  # noqa: F401  保证建表时模型已注册
from utils.errors import ApiError
from utils.response import Code, fail

from routes.api_auth import bp as api_auth_bp
from routes.api_misc import bp as api_misc_bp
from routes.api_notes import bp as api_notes_bp
from routes.api_social import bp as api_social_bp
from routes.pages import bp as pages_bp


def create_app(config_object=Config, **overrides):
    app = Flask(__name__, instance_path=getattr(config_object, "INSTANCE_DIR", None))
    app.config.from_object(config_object)
    app.config.update(overrides)

    # 中文不做 \uXXXX 转义
    app.json.ensure_ascii = False

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "pages.login"
    login_manager.login_message = "请先登录"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return fail(err.code, err.message)

    @app.errorhandler(413)
    def handle_file_too_large(err):
        return fail(Code.UPLOAD_TOO_LARGE, "图片大小不能超过 5MB")

    @app.errorhandler(404)
    def handle_not_found(err):
        if request.path.startswith("/api/"):
            return fail(Code.NOT_FOUND, "内容不存在或已被删除")
        return render_template("404.html"), 404

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        if isinstance(err, HTTPException):
            return err
        app.logger.exception("未处理异常: %s", err)
        return fail(Code.SERVER_ERROR, "服务器繁忙，请稍后重试", http=500)

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_auth_bp)
    app.register_blueprint(api_notes_bp)
    app.register_blueprint(api_social_bp)
    app.register_blueprint(api_misc_bp)

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
