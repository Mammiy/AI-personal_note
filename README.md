# 个人笔记

一款简洁优雅的个人在线笔记应用：注册登录、Markdown 写作与发布、分享、评论、收藏、个人主页，以及划词右键 AI 润色。

技术栈：Python 3.12 + Flask + SQLite，前端为原生 HTML / CSS / JavaScript（无构建步骤）。

## 快速开始

### 1. 创建并激活虚拟环境

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. 安装依赖（清华镜像）

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

开发依赖（仅测试需要）：

```bash
pip install -r requirements-dev.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 启动应用

方式一，直接运行：

```bash
python app.py
```

方式二（Windows），双击项目根目录的 `start.bat`：脚本会依次检查 Python 与依赖、探测可用端口、在独立窗口启动服务、轮询 `/api/health` 就绪后自动打开浏览器；服务已运行时只打开浏览器，不会重复拉起第二个实例。候选端口顺序为 `5000 → 5057 → 5067 → 5087`（可用 `APP_PORT` 覆盖）。

打开 <http://127.0.0.1:5000> 即可访问。首次启动会自动创建数据库文件 `instance/notes.db` 与上传目录 `static/uploads/`。

若 5000 端口被系统或其他程序占用（Windows 下可能提示 `WinError 10013`），改用其他端口启动：

```bash
# Windows PowerShell
$env:APP_PORT="5057"; python app.py
# macOS / Linux / Git Bash
APP_PORT=5057 python app.py
```

### 4. 运行测试

```bash
python -m pytest tests -q
```

前端纯逻辑（`api.js`、编辑器文本变换、列表筛选、Markdown 渲染管线）用 Node 内置测试运行器：

```bash
node --test "tests/js/*.test.js"
```

## 前端第三方库

Markdown 渲染与消毒使用本地 vendor 库，不依赖外部 CDN，版本锁定如下：

| 库 | 版本 | 文件 |
|---|---|---|
| marked | 18.0.14 | `static/js/vendor/marked.umd.js` |
| DOMPurify | 3.4.16 | `static/js/vendor/purify.min.js` |

下载来源：

```bash
curl -L -o static/js/vendor/marked.umd.js https://cdn.jsdelivr.net/npm/marked@18.0.14/lib/marked.umd.js
curl -L -o static/js/vendor/purify.min.js https://cdn.jsdelivr.net/npm/dompurify@3.4.16/dist/purify.min.js
```

正文只在前端渲染一次：`renderMarkdown()`（`static/js/markdown.js`）先由 marked 解析，再交给 DOMPurify 消毒，预览与详情页共用。

## 配置说明

| 配置项 | 环境变量 | 默认值 | 说明 |
|---|---|---|---|
| `SECRET_KEY` | `SECRET_KEY` | 自动生成并写入 `instance/secret.key` | 会话签名密钥，请勿提交到仓库 |
| 监听地址 / 端口 | `APP_HOST` / `APP_PORT` | `127.0.0.1` / `5000` | 开发服务器绑定地址，端口被占用时可覆盖 |
| `AI_BASE_URL` | `AI_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容的大模型接口地址 |
| `AI_API_KEY` | `AI_API_KEY` | 空 | 大模型密钥，仅存于服务端环境变量 |
| `AI_MODEL` | `AI_MODEL` | `deepseek-chat` | 模型名称 |

AI 润色密钥通过环境变量注入，不要写进代码或提交到仓库：

```bash
# Windows PowerShell
$env:AI_API_KEY="sk-xxxxxx"
# macOS / Linux / Git Bash
export AI_API_KEY="sk-xxxxxx"
```

未配置 `AI_API_KEY` 时，AI 润色会自动回退为本地**确定性规则改写**（等价词替换 + 冗余精简 + 中文标点规范化，结果区标注「模拟结果」），功能流程完整可用、结果可复现；如需真实模型润色效果，配置密钥后重启即可。

大模型密钥只从环境变量读取，`.env` 一类本地文件已在 `.gitignore` 中排除，切勿把密钥写进代码或提交到仓库。

## 目录结构

```
app.py                 应用工厂
config.py              配置
extensions.py          db / login_manager 实例
models.py              数据模型
routes/                页面路由与 /api/* 路由
services/              业务规则
utils/                 统一响应与异常
templates/             Jinja 模板
static/css|js|img      样式、脚本、图片素材
tests/                 pytest 用例
docs/                  需求与设计文档、分阶段实施计划
提示词/                 原始需求提示词（随仓库提交）
start.bat              Windows 一键启动脚本
```

参考材料处理：`图片素材/`（主页与纸张背景原图）与 `项目截图/`（界面参考截图）仅作本地比对使用，已在 `.gitignore` 中排除；应用实际引用的背景图已复制到 `static/img/`，随代码提交。

## 编码约定

全链路 UTF-8：源码、模板、静态文件、HTTP 响应均使用 UTF-8，不使用 GBK。
