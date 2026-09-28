/**
 * editor.js 行为测试（Node 内置 test runner，零依赖）。
 * 运行：node --test tests/js/editor.test.js
 *
 * 工具栏的全部文本变换都是纯函数，不碰 DOM，因此可以在 Node 里直接验证。
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const EDITOR_PATH = path.join(__dirname, "..", "..", "static", "js", "editor.js");

function loadEditor() {
  const sandbox = { console, JSON, String, Array, Object };
  sandbox.window = {};
  const context = vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(EDITOR_PATH, "utf8"), context, {
    filename: "editor.js",
  });
  return sandbox.window.Editor;
}

const Editor = loadEditor();

// ---------- 包裹类 ----------

test("加粗包裹选区并保持选中原文", () => {
  const result = Editor.wrap("你好世界", 0, 2, "**");

  assert.equal(result.value, "**你好**世界");
  assert.equal(result.value.slice(result.start, result.end), "你好");
});

test("行内代码包裹选区", () => {
  const result = Editor.wrap("用 code 表示", 2, 6, "`");

  assert.equal(result.value, "用 `code` 表示");
  assert.equal(result.value.slice(result.start, result.end), "code");
});

test("无选区时插入成对标记并把光标放在中间", () => {
  const result = Editor.wrap("abc", 3, 3, "**");

  assert.equal(result.value, "abc****");
  assert.equal(result.start, 5);
  assert.equal(result.end, 5);
});

test("包裹不影响选区之外的内容", () => {
  const result = Editor.wrap("前缀|中段|后缀", 3, 5, "**");

  assert.equal(result.value, "前缀|**中段**|后缀");
});

// ---------- 行前缀类 ----------

test("无序列表给每个选中行加前缀", () => {
  const result = Editor.prefixLines("第一\n第二\n第三", 0, 5, "- ");

  assert.equal(result.value, "- 第一\n- 第二\n第三");
});

test("标题前缀只作用于光标所在行", () => {
  const result = Editor.prefixLines("abc\ndef", 1, 1, "# ");

  assert.equal(result.value, "# abc\ndef");
});

test("已带前缀时再次点击移除前缀", () => {
  const result = Editor.prefixLines("- 第一\n- 第二", 0, 9, "- ");

  assert.equal(result.value, "第一\n第二");
});

test("有序列表给每行加 1. 前缀", () => {
  const result = Editor.prefixLines("甲\n乙", 0, 3, "1. ");

  assert.equal(result.value, "1. 甲\n1. 乙");
});

test("行前缀返回的新选区覆盖整块改动", () => {
  const result = Editor.prefixLines("甲\n乙", 0, 3, "> ");

  assert.equal(result.start, 0);
  assert.equal(result.end, result.value.length);
});

// ---------- 插入链接与图片 ----------

test("插入链接用选中文字并选中 url 占位", () => {
  const result = Editor.insertLink("看 文档 吧", 2, 4);

  assert.equal(result.value, "看 [文档](url) 吧");
  assert.equal(result.value.slice(result.start, result.end), "url");
});

test("无选区时插入链接使用默认文字", () => {
  const result = Editor.insertLink("", 0, 0);

  assert.equal(result.value, "[文字](url)");
  assert.equal(result.value.slice(result.start, result.end), "url");
});

test("插入图片链接保留说明文字", () => {
  const result = Editor.insertImage("正文", 2, 2, "/static/uploads/a.png", "风景");

  assert.equal(result.value, "正文![风景](/static/uploads/a.png)");
  assert.equal(result.start, result.value.length);
});

test("本地上传插入无说明的图片语法", () => {
  const result = Editor.insertImage("开头", 0, 0, "/static/uploads/b.jpg", "");

  assert.equal(result.value, "![](/static/uploads/b.jpg)开头");
});

test("插入图片会替换选区内容", () => {
  const result = Editor.insertImage("删掉我", 0, 3, "/u/c.png", "图");

  assert.equal(result.value, "![图](/u/c.png)");
});
