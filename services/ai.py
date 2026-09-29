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

# 模拟润色的词替换表：单趟最长优先匹配，避免「不错→很好」又被「很好→相当好」二次改写。
# 只收录语义等价、口语到书面方向的常见词对，保证不改原意、不引入新事实。
WORD_MAP = (
    ("然后", "随后"),
    ("但是", "然而"),
    ("因为", "由于"),
    ("所以", "因此"),
    ("而且", "并且"),
    ("我觉得", "我认为"),
    ("觉得", "认为"),
    ("其实", "事实上"),
    ("非常", "极为"),
    ("特别", "尤为"),
    ("很多", "诸多"),
    ("一些", "若干"),
    ("现在", "当前"),
    ("想要", "希望"),
    ("应该", "应当"),
    ("可能", "也许"),
    ("就像", "犹如"),
    ("好像", "仿佛"),
    ("一直", "始终"),
    ("有点", "有些"),
    ("越来越", "日益"),
    ("真的", "确实"),
    ("差不多", "大致"),
    ("的时候", "时"),
    ("一起", "共同"),
    ("看一下", "查看"),
    ("讲了", "讲述了"),
    ("主要", "着重"),
    ("使人", "让人"),
    ("思考", "深思"),
    ("感悟", "体悟"),
    ("表示", "表明"),
    ("提高", "提升"),
    ("感觉", "感到"),
    ("不错", "很好"),
    ("很好", "相当好"),
    ("很", "相当"),
)

# 冗余表达精简：只删不改，语义不变
REDUNDANT_MAP = (
    ("的的", "的"),
    ("了了", "了"),
    ("有着", "有"),
    ("的话，", "，"),
    ("的话。", "。"),
)

CJK = "\u4e00-\u9fff"

# 这些行只做空白规范化，不做改写，避免破坏 Markdown 标记
STRUCTURAL_PREFIXES = ("#", ">", "-", "*", "|")
ORDERED_ITEM_RE = re.compile(r"^\d+\.")

CN_PUNCTUATION_RE = re.compile(r"([，。、；：！？）】》”])\s+")
CN_PUNCTUATION_BEFORE_RE = re.compile(r"\s+([，。、；：！？）】》”])")
SPACES_RE = re.compile(r"[ \t]{2,}")
# 中文语境（前一字符是汉字）里的半角标点转全角；英文与链接不受影响
HALF_PUNCTUATION_RE = re.compile(rf"(?<=[{CJK}])([,.;:?!])")
HALF_PUNCTUATION_MAP = {",": "，", ".": "。", ";": "；", ":": "：", "?": "？", "!": "！"}
ELLIPSIS_RE = re.compile(rf"(?<=[{CJK}])(?:\.{{3,}}|。{{3,}})")
DUP_PUNCTUATION_RE = re.compile(r"([，。、；：！？])\1+")

_WORD_RE = re.compile(
    "|".join(
        re.escape(source) for source in sorted((s for s, _ in WORD_MAP), key=len, reverse=True)
    )
)
_WORD_LOOKUP = dict(WORD_MAP)
_REDUNDANT_RE = re.compile(
    "|".join(
        re.escape(source)
        for source in sorted((s for s, _ in REDUNDANT_MAP), key=len, reverse=True)
    )
)
_REDUNDANT_LOOKUP = dict(REDUNDANT_MAP)


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
    """本地确定性规则改写：结构行与代码块只做空白规范化，其余行做词替换与标点规范化。

    这里是未配置大模型时的降级实现，必须对普通文章产生可见改写（否则「确认替换」
    后正文与原文一字不差，功能看起来是坏的），同时保持不改原意、不引入新事实。
    """
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
            lines.append(_normalize_spaces(_polish_line(line)))

    return "\n".join(lines)


def _is_structural(line):
    stripped = line.lstrip()
    if not stripped:
        return True
    return stripped[0] in STRUCTURAL_PREFIXES or bool(ORDERED_ITEM_RE.match(stripped))


def _polish_line(line):
    """单行改写顺序：词替换 → 冗余精简 → 标点规范化，每步都只做一趟。"""
    return _normalize_punctuation(_replace_words(_trim_redundancy(line)))


def _replace_words(line):
    return _WORD_RE.sub(lambda match: _WORD_LOOKUP[match.group(0)], line)


def _trim_redundancy(line):
    return _REDUNDANT_RE.sub(lambda match: _REDUNDANT_LOOKUP[match.group(0)], line)


def _normalize_punctuation(line):
    """省略号归一 → 中文语境半角标点转全角 → 重复标点合并。"""
    line = ELLIPSIS_RE.sub("……", line)
    line = HALF_PUNCTUATION_RE.sub(lambda m: HALF_PUNCTUATION_MAP[m.group(1)], line)
    return DUP_PUNCTUATION_RE.sub(r"\1", line)


def _normalize_spaces(line):
    """合并行内连续空格、去除行尾空格与中文标点前后的多余空格，保留行首缩进。"""
    stripped = line.rstrip()
    if not stripped:
        return ""

    indent = stripped[: len(stripped) - len(stripped.lstrip())]
    body = stripped[len(indent) :]
    body = SPACES_RE.sub(" ", body)
    body = CN_PUNCTUATION_RE.sub(r"\1", body)
    body = CN_PUNCTUATION_BEFORE_RE.sub(r"\1", body)

    return indent + body
