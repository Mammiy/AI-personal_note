"""pytest 公共夹具：内存数据库 + 测试客户端。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402


@pytest.fixture
def app():
    application = create_app(
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        TESTING=True,
        PROPAGATE_EXCEPTIONS=False,
    )
    with application.app_context():
        db.create_all()
        yield application
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    """在应用上下文内直接操作数据库的会话。"""
    with app.app_context():
        yield db.session
