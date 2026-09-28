"""AI 润色服务：提示词构造、模型调用、错误映射、模拟回退与频率限制。

密钥只在服务端读取，既不写进响应也不写进 message；异常堆栈一律不对外暴露。
未配置密钥时走本地确定性模拟，保证功能流程在无外网环境下仍完整可演示。
"""

import re
import time

import requests
from flask import current_app
from flask_login import current_user

from utils.errors import ApiError
from utils.response import Code

SYSTEM_PROMPT = (
    "你是一位中文写作润色助手。请对用户输入文本进行润色：提升流畅度、清晰度与表达质量；"
    "不改变原意，不添加原文没有的事实；保持原文语言不变；"
    "完整保留 Markdown 标记（标题、列表、引用、代码块、链接、图片）与段落结构；"
    "只输出润色后的文本本身，不要输出任何解释、标题、前后缀或代码块围栏。"
)

# 模拟润色说明文案（对应需求文档「AI 未配置」一条）
SIMULATE_HINT = "尚未配置大模型，当前展示模拟润色结果"

TEMPERATURE = 0.3
MAX_TOKENS = 8192

# 频率限制：同一用户 60 秒内最多 10 次，防滥用
RATE_LIMIT = 10
RATE_WINDOW = 60
_RATE = {}

# 模拟润色的词替换表：有序、每轮只替换一次，保证同一输入结果一致
WORD_MAP = (
    ("然后", "随后"),
    ("但是", "然而"),
    ("因为", "由于"),
    ("所以", "因此"),
    ("我觉得", "我认为"),
    ("其实", "事实上"),
    ("非常", "极为"),
    ("特别", "尤为"),
    ("很多", "诸多"),
    ("一些", "若干"),
    ("现在", "当前"),
)

# 这些行只做空白规范化，不做词替换，避免破坏 Markdown 标记
STRUCTURAL_PREFIXES = ("#", ">", "-", "*", "|")
ORDERED_ITEM_RE = re.compile(r"^\d+\.")

CN_PUNCTUATION_RE = re.compile(r"([，。、；：！？）】》”])\s+")
SPACES_RE = re.compile(r"[ \t]{2,}")


def polish(text):
    """润色选中文本，返回 (润色后文本, 是否为模拟结果)。"""
    cfg = current_app.config

    if not text or not text.strip():
        raise ApiError(Code.PARAM_ERROR, "请先选中要润色的文本")
    if len(text) > cfg["AI_MAX_CHARS"]:
        raise ApiError(Code.PARAM_ERROR, "选中内容过长，请分段润色")

    _check_rate(current_user.id)

    if not cfg["AI_API_KEY"]:
        return _simulate(text), True

    content = _call_model(text, cfg)
    if not content:
        raise ApiError(Code.AI_ERROR, "未能生成润色结果，请调整选中内容后重试")

    return _strip_fence(content), False


def _check_rate(user_id):
    """同一用户 60 秒内超过 10 次直接拒绝，避免接口被当作通用文本接口滥用。"""
    now = time.time()
    stamps = [t for t in _RATE.get(user_id, []) if now - t < RATE_WINDOW]

    if len(stamps) >= RATE_LIMIT:
        _RATE[user_id] = stamps
        raise ApiError(Code.AI_ERROR, "润色请求过于频繁，请稍后再试")

    stamps.append(now)
    _RATE[user_id] = stamps


def _call_model(text, cfg):
    """调用 OpenAI 兼容的对话补全接口，异常统一映射为中文业务错误。"""
    url = cfg["AI_BASE_URL"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": "Bearer " + cfg["AI_API_KEY"],
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg["AI_MODEL"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    try:
        resp = requests.post(
            url, headers=headers, json=payload, timeout=cfg["AI_TIMEOUT"]
        )
    except requests.Timeout:
        raise ApiError(Code.AI_TIMEOUT, "润色请求超时，请稍后重试")
    except requests.RequestException:
        raise ApiError(Code.AI_ERROR, "润色失败，请稍后重试")

    if resp.status_code != 200:
        raise ApiError(Code.AI_ERROR, "润色失败，请稍后重试")

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (ValueError, TypeError, KeyError, IndexError):
        raise ApiError(Code.AI_ERROR, "润色失败，请稍后重试")

    return (content or "").strip()


def _strip_fence(text):
    """去掉模型偶尔返回的首尾 ``` 围栏与多余空行。"""
    s = (text or "").strip()

    if s.startswith("```"):
        s = s.partition("\n")[2]
    if s.rstrip().endswith("```"):
        s = s.rstrip()[:-3]

    return s.strip()


def _simulate(text):
    """本地确定性规则改写：结构行与代码块只做空白规范化，其余行做词替换。"""
    in_code = False
    lines = []

    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            lines.append(_normalize_spaces(line))
            continue

        if in_code or _is_structural(line):
            lines.append(_normalize_spaces(line))
        else:
            lines.append(_normalize_spaces(_replace_words(line)))

    return "\n".join(lines)


def _is_structural(line):
    stripped = line.lstrip()
    if not stripped:
        return True
    return stripped[0] in STRUCTURAL_PREFIXES or bool(ORDERED_ITEM_RE.match(stripped))


def _replace_words(line):
    for source, target in WORD_MAP:
        line = line.replace(source, target)
    return line


def _normalize_spaces(line):
    """合并行内连续空格、去除行尾空格与中文标点后的多余空格，保留行首缩进。"""
    stripped = line.rstrip()
    if not stripped:
        return ""

    indent = stripped[: len(stripped) - len(stripped.lstrip())]
    body = stripped[len(indent) :]
    body = SPACES_RE.sub(" ", body)
    body = CN_PUNCTUATION_RE.sub(r"\1", body)

    return indent + body
