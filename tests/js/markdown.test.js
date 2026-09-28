/**
 * markdown.js 行为测试（Node 内置 test runner，零依赖）。
 * 运行：node --test tests/js/markdown.test.js
 *
 * 说明：DOMPurify 依赖真实 DOM，Node 环境下没有 document，
 * 因此"消毒是否真的拦住 XSS"只能在浏览器中验证（见文件末尾 test 的注释）。
 * 这里覆盖的是：真实 marked 渲染结果 + 渲染与消毒的组合顺序。
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const JS_DIR = path.join(__dirname, "..", "..", "static", "js");
const MARKED_PATH = path.join(JS_DIR, "vendor", "marked.umd.js");
const PURIFY_PATH = path.join(JS_DIR, "vendor", "purify.min.js");
const RENDER_PATH = path.join(JS_DIR, "markdown.js");

/** 沙箱需要的标准库（marked 会用到其中一部分） */
function baseSandbox() {
  const sandbox = {
    console,
    JSON,
    Error,
    TypeError,
    RegExp,
    String,
    Array,
    Object,
    Math,
    Date,
    Set,
    Map,
    Promise,
    Symbol,
    parseInt,
    parseFloat,
    isNaN,
    encodeURI,
    decodeURI,
    encodeURIComponent,
    decodeURIComponent,
  };
  sandbox.globalThis = sandbox;
  return sandbox;
}

/** 加载真实 marked（不注入任何替身） */
function loadRealMarked() {
  const sandbox = baseSandbox();
  const context = vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(MARKED_PATH, "utf8"), context, {
    filename: "marked.umd.js",
  });
  return sandbox.marked;
}

/**
 * 加载 markdown.js：真实 marked + DOMPurify 替身（记录调用参数）。
 * 替身返回的 html 原样透出，便于断言"消毒结果就是最终返回值"。
 */
function loadRenderer({ sanitize } = {}) {
  const sanitizeCalls = [];
  const sandbox = baseSandbox();
  const context = vm.createContext(sandbox);

  vm.runInContext(fs.readFileSync(MARKED_PATH, "utf8"), context, {
    filename: "marked.umd.js",
  });

  sandbox.DOMPurify = {
    sanitize: (html, cfg) => {
      sanitizeCalls.push({ html, cfg });
      return sanitize ? sanitize(html) : html;
    },
  };
  sandbox.window = {};

  vm.runInContext(fs.readFileSync(RENDER_PATH, "utf8"), context, {
    filename: "markdown.js",
  });

  return { renderMarkdown: sandbox.window.renderMarkdown, sanitizeCalls };
}

test("vendor 文件可用：marked 与 DOMPurify 都能挂到全局", () => {
  const sandbox = baseSandbox();
  const context = vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(MARKED_PATH, "utf8"), context);
  vm.runInContext(fs.readFileSync(PURIFY_PATH, "utf8"), context);

  assert.equal(typeof sandbox.marked, "object", "marked 应暴露为对象");
  // DOMPurify 在没有 DOM 的环境里 isSupported 为 false，但库本身必须能加载
  assert.equal(typeof sandbox.DOMPurify, "function", "DOMPurify 应能加载");
});

test("真实 marked 能渲染标题、粗体、列表与图片", () => {
  const marked = loadRealMarked();
  marked.setOptions({ gfm: true, breaks: true });

  const html = marked.parse("# 标题\n**粗体**\n- 列表\n\n![](x.png)");

  assert.match(html, /<h1[^>]*>标题<\/h1>/);
  assert.match(html, /<strong>粗体<\/strong>/);
  assert.match(html, /<li>列表<\/li>/);
  assert.match(html, /<img src="x.png"/);
});

test("renderMarkdown 把 marked 的输出交给 DOMPurify 消毒", () => {
  const { renderMarkdown, sanitizeCalls } = loadRenderer();

  renderMarkdown("# 标题\n**粗体**\n- 列表\n\n![](x.png)");

  assert.equal(sanitizeCalls.length, 1, "一次渲染只消毒一次");
  const html = sanitizeCalls[0].html;
  assert.match(html, /<h1[^>]*>标题<\/h1>/);
  assert.match(html, /<strong>粗体<\/strong>/);
  assert.match(html, /<li>列表<\/li>/);
  assert.match(html, /<img src="x.png"/);
});

test("消毒配置保留图片 alt 与链接 title", () => {
  const { renderMarkdown, sanitizeCalls } = loadRenderer();

  renderMarkdown("![风景](/u/a.png)");

  const cfg = sanitizeCalls[0].cfg;
  // 沙箱内数组的原型跨 realm，先拷回宿主 realm 再断言
  assert.deepEqual({ ADD_ATTR: Array.from(cfg.ADD_ATTR) }, { ADD_ATTR: ["alt", "title"] });
  assert.deepEqual(Array.from(Object.keys(cfg)), ["ADD_ATTR"]);
});

test("返回的是消毒后的结果，不做二次加工", () => {
  const { renderMarkdown } = loadRenderer({
    sanitize: (html) => html.replace(/<script[\s\S]*?<\/script>/gi, ""),
  });

  const out = renderMarkdown('<script>alert(1)</script>\n\n# 标题');

  assert.equal(out.includes("<script"), false);
  assert.match(out, /<h1[^>]*>标题<\/h1>/);
});

test("空值与空字符串渲染为空，不抛异常", () => {
  const { renderMarkdown, sanitizeCalls } = loadRenderer();

  assert.equal(renderMarkdown(""), "");
  assert.equal(renderMarkdown(null), "");
  assert.equal(renderMarkdown(undefined), "");
  assert.deepEqual(
    sanitizeCalls.map((call) => call.html),
    ["", "", ""]
  );
});

test("marked 本身不消毒，脚本标签会原样输出（消毒不可省略）", () => {
  const marked = loadRealMarked();

  const html = marked.parse('<script>alert(1)</script>');

  assert.match(html, /<script>alert\(1\)<\/script>/);
  // 浏览器中的等价验证（DOMPurify 需要真实 DOM，Node 无法执行）：
  // renderMarkdown('<img src=x onerror="alert(1)">') 输出不得含 onerror / javascript:；
  // renderMarkdown('<script>alert(1)</script>') 输出不得含 <script> 标签。
});
