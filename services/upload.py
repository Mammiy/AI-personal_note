"""图片上传：扩展名白名单、随机文件名落盘、返回静态可访问地址。

不使用原始文件名，避免覆盖已有文件与路径穿越。"""

import os
import uuid

from flask import current_app
from utils.errors import ApiError
from utils.response import Code

TYPE_MESSAGE = "仅支持 png、jpg、jpeg、webp、gif 格式的图片"


def save_image(file):
    """校验扩展名 → 生成随机文件名 → 落盘 → 返回可访问地址。"""
    filename = file.filename or ""
    if "." not in filename:
        raise ApiError(Code.UPLOAD_TYPE_ERROR, TYPE_MESSAGE)

    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in current_app.config["ALLOWED_IMAGE_EXT"]:
        raise ApiError(Code.UPLOAD_TYPE_ERROR, TYPE_MESSAGE)

    name = f"{uuid.uuid4().hex}.{ext}"
    folder = current_app.config["UPLOAD_FOLDER"]
    try:
        os.makedirs(folder, exist_ok=True)
        file.save(os.path.join(folder, name))
    except OSError:
        current_app.logger.exception("图片写盘失败: %s", filename)
        raise ApiError(Code.SERVER_ERROR, "图片上传失败，请稍后重试")

    return f"/static/uploads/{name}"
