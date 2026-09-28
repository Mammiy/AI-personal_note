/**
 * ai_polish.js 行为测试（Node 内置 test runner，零依赖）。
 * 运行：node --test tests/js/ai_polish.test.js
 *
 * 本环境没有浏览器，弹窗的 DOM 行为用一个最小 DOM 替身驱动：
 * 替身只实现 ai_polish.js 真正用到的那几个属性（value/textContent/hidden/disabled/
 * classList/focus/setSelectionRange/addEventListener），断言的是可见行为而不是替身自身。
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const TARGET = path.join(__dirname, "..", "..", "static", "js", "ai_polish.js");

// ---------- 最小 DOM 替身 ----------

function makeElement(doc, id) {
  const handlers = {};
  return {
    id,
    value: "",
    textContent: "",
    hidden: true,
    disabled: false,
    selectionStart: 0,
    selectionEnd: 0,
    _handlers: handlers,
    classList: {
      _set: new Set(),
      add(name) {
        this._set.add(name);
      },
      remove(name) {
        this._set.delete(name);
      },
      contains(name) {
        return this._set.has(name);
      },
    },
    addEventListener(type, fn) {
      (handlers[type] = handlers[type] || []).push(fn);
    },
    removeEventListener(type, fn) {
      handlers[type] = (handlers[type] || []).filter((item) => item !== fn);
    },
    dispatch(type, event) {
      (handlers[type] || []).slice().forEach((fn) => fn(event));
    },
    click() {
      this.dispatch("click", { target: this, preventDefault() {} });
    },
    focus() {
      doc.activeElement = this;
    },
    setSelectionRange(start, end) {
      this.selectionStart = start;
      this.selectionEnd = end;
    },
    dispatchEvent(event) {
      this.dispatch(event.type, event);
    },
  };
}

function makeDocument() {
  const nodes = new Map();
  const handlers = {};
  const doc = {
    activeElement: null,
    _handlers: handlers,
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, makeElement(doc, id));
      return nodes.get(id);
    },
    addEventListener(type, fn) {
      (handlers[type] = handlers[type] || []).push(fn);
    },
    removeEventListener(type, fn) {
      handlers[type] = (handlers[type] || []).filter((item) => item !== fn);
    },
    fire(type, event) {
      (handlers[type] || []).slice().forEach((fn) => fn(event));
    },
  };
  return doc;
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** 微任务全部跑完，避免靠固定等待判断异步结果。 */
const flush = () => new Promise((resolve) => setImmediate(resolve));

/** 每个用例一份全新环境：DOM、Api、Toast 全部隔离。 */
function harness({ post } = {}) {
  const doc = makeDocument();
  const toasts = [];
  const requests = [];

  // 与模板保持一致：按钮与原文框初始可见，加载/结果/错误区初始隐藏
  ["ai-polish-close", "ai-polish-cancel", "ai-polish-confirm", "ai-polish-source"].forEach(
    (id) => {
      doc.getElementById(id).hidden = false;
    }
  );

  const apiPost =
    post ||
    ((requestPath, body) => {
      requests.push({ path: requestPath, body });
      return Promise.resolve({ text: "润色结果", simulated: false });
    });

  const win = {};
  const toast = {
    show(message, type) {
      toasts.push({ message, type });
    },
  };

  // 用 new Function 而不是 vm：与测试同处一个 realm，断言里的对象比较才成立
  const factory = new Function(
    "window",
    "document",
    "Api",
    "Toast",
    fs.readFileSync(TARGET, "utf8")
  );
  factory(win, doc, { post: apiPost }, toast);

  return {
    AiPolish: win.AiPolish,
    doc,
    el: (id) => doc.getElementById(id),
    toasts,
    requests,
  };
}

/** 造一个带选区的 textarea，并把它设为当前焦点。 */
function textarea(doc, value, start, end) {
  const el = doc.getElementById("content");
  el.value = value;
  el.selectionStart = start;
  el.selectionEnd = end;
  doc.activeElement = el;
  return el;
}

function countHandlers(node, type) {
  return (node._handlers[type] || []).length;
}

// ---------- 纯函数 ----------

test("确认替换只改写选区，前后内容一字不动", () => {
  const { AiPolish } = harness();

  const result = AiPolish.replaceSelection("AAABBBCCC", 3, 6, "XYZ");

  assert.equal(result.value, "AAAXYZCCC");
  assert.equal(result.caret, 6);
});

test("确认替换后光标停在替换内容末尾", () => {
  const { AiPolish } = harness();

  const result = AiPolish.replaceSelection("前缀中缀后缀", 2, 4, "润色后的长文本");

  assert.equal(result.caret, 2 + "润色后的长文本".length);
});

test("空选区时替换等同于在光标处插入", () => {
  const { AiPolish } = harness();

  const result = AiPolish.replaceSelection("ab", 1, 1, "X");

  assert.equal(result.value, "aXb");
  assert.equal(result.caret, 2);
});

test("无选区时菜单项判定为不可用", () => {
  const { AiPolish } = harness();

  assert.equal(AiPolish.hasSelection(4, 4), false);
  assert.equal(AiPolish.hasSelection(4, 9), true);
});

test("菜单贴边时会被拉回视口内", () => {
  const { AiPolish } = harness();

  const pos = AiPolish.menuPosition(1900, 1070, 160, 48, 1920, 1080);

  assert.deepEqual(pos, { left: 1760, top: 1032 });
});

test("菜单在正常位置时不偏移", () => {
  const { AiPolish } = harness();

  const pos = AiPolish.menuPosition(100, 200, 160, 48, 1920, 1080);

  assert.deepEqual(pos, { left: 100, top: 200 });
});

test("Shift+F10 与 ContextMenu 键都能唤起菜单", () => {
  const { AiPolish } = harness();

  assert.equal(AiPolish.isMenuKey({ key: "F10", shiftKey: true }), true);
  assert.equal(AiPolish.isMenuKey({ key: "ContextMenu" }), true);
  assert.equal(AiPolish.isMenuKey({ key: "F10", shiftKey: false }), false);
  assert.equal(AiPolish.isMenuKey({ key: "a", shiftKey: true }), false);
});

test("Tab 在弹窗内循环，Shift+Tab 反向循环", () => {
  const { AiPolish } = harness();

  assert.equal(AiPolish.nextFocusIndex(0, 3, 1), 1);
  assert.equal(AiPolish.nextFocusIndex(2, 3, 1), 0);
  assert.equal(AiPolish.nextFocusIndex(0, 3, -1), 2);
  assert.equal(AiPolish.nextFocusIndex(-1, 3, 1), 0);
});

test("只有成功态才允许确认替换", () => {
  const { AiPolish } = harness();

  assert.equal(AiPolish.canConfirm("loading"), false);
  assert.equal(AiPolish.canConfirm("error"), false);
  assert.equal(AiPolish.canConfirm("success"), true);
});

test("模拟结果才显示徽标，真实结果不显示", () => {
  const { AiPolish } = harness();

  assert.equal(AiPolish.badgeText(true), "模拟结果");
  assert.equal(AiPolish.badgeText(false), "");
});

// ---------- 弹窗状态机 ----------

test("打开弹窗即进入加载态：左栏原文、润色中、确认替换禁用", async () => {
  const pending = deferred();
  const env = harness({ post: () => pending.promise });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  const opening = env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });

  assert.equal(env.el("ai-polish-mask").hidden, false);
  assert.equal(env.el("ai-polish-source").value, "BBB");
  assert.equal(env.el("ai-polish-loading").hidden, false);
  assert.equal(env.el("ai-polish-loading-text").textContent, "润色中…");
  assert.equal(env.el("ai-polish-result").hidden, true);
  assert.equal(env.el("ai-polish-error").hidden, true);
  assert.equal(env.el("ai-polish-confirm").disabled, true);

  pending.resolve({ text: "润色结果", simulated: true });
  await opening;
});

test("打开弹窗只把选中的文本发给后端", async () => {
  const env = harness();
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });

  assert.deepEqual(env.requests, [{ path: "/api/ai/polish", body: { text: "BBB" } }]);
});

test("成功且为模拟结果时展示文本、徽标与说明，确认替换可用", async () => {
  const env = harness({
    post: () => Promise.resolve({ text: "随后我认为这个极为好", simulated: true }),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });

  assert.equal(env.el("ai-polish-loading").hidden, true);
  assert.equal(env.el("ai-polish-error").hidden, true);
  assert.equal(env.el("ai-polish-result").hidden, false);
  assert.equal(env.el("ai-polish-result").value, "随后我认为这个极为好");
  assert.equal(env.el("ai-polish-badge").textContent, "模拟结果");
  assert.equal(env.el("ai-polish-badge").hidden, false);
  assert.equal(
    env.el("ai-polish-hint").textContent,
    "尚未配置大模型，当前展示模拟润色结果"
  );
  assert.equal(env.el("ai-polish-confirm").disabled, false);
});

test("真实模型结果不显示模拟徽标与说明", async () => {
  const env = harness({
    post: () => Promise.resolve({ text: "润色结果", simulated: false }),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });

  assert.equal(env.el("ai-polish-badge").hidden, true);
  assert.equal(env.el("ai-polish-hint").textContent, "");
  assert.equal(env.el("ai-polish-confirm").disabled, false);
});

test("失败时显示后端文案与重试，原文保留且确认替换禁用", async () => {
  const env = harness({
    post: () => Promise.reject(new Error("润色失败，请稍后重试")),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });

  assert.equal(env.el("ai-polish-loading").hidden, true);
  assert.equal(env.el("ai-polish-error").hidden, false);
  assert.equal(env.el("ai-polish-error").textContent, "润色失败，请稍后重试");
  assert.equal(env.el("ai-polish-retry").hidden, false);
  assert.equal(env.el("ai-polish-confirm").disabled, true);
  assert.equal(env.el("ai-polish-source").value, "BBB");
  assert.equal(el.value, "AAABBBCCC");
});

test("失败后点重试会重新请求，成功后展示结果", async () => {
  let attempt = 0;
  const env = harness({
    post: () => {
      attempt += 1;
      return attempt === 1
        ? Promise.reject(new Error("润色请求超时，请稍后重试"))
        : Promise.resolve({ text: "重试后的结果", simulated: true });
    },
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });

  env.el("ai-polish-retry").click();
  await flush();

  assert.equal(attempt, 2);
  assert.equal(env.el("ai-polish-result").value, "重试后的结果");
  assert.equal(env.el("ai-polish-error").hidden, true);
  assert.equal(env.el("ai-polish-confirm").disabled, false);
});

// ---------- 确认替换 ----------

test("确认替换把结果写回原选区并提示成功", async () => {
  const env = harness({
    post: () => Promise.resolve({ text: "XYZ", simulated: false }),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });
  env.el("ai-polish-confirm").click();

  assert.equal(el.value, "AAAXYZCCC");
  assert.equal(el.selectionStart, 6);
  assert.equal(el.selectionEnd, 6);
  assert.deepEqual(env.toasts, [{ message: "已替换选中的文本", type: "success" }]);
  assert.equal(env.el("ai-polish-mask").hidden, true);
});

test("连续快速点击确认替换只回写一次", async () => {
  const env = harness({
    post: () => Promise.resolve({ text: "XYZ", simulated: false }),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });
  env.el("ai-polish-confirm").click();
  env.el("ai-polish-confirm").click();
  env.el("ai-polish-confirm").click();

  assert.equal(el.value, "AAAXYZCCC");
  assert.equal(env.toasts.length, 1);
});

test("替换后触发一次 input 事件，预览与保存能拿到最新内容", async () => {
  const env = harness({
    post: () => Promise.resolve({ text: "XYZ", simulated: false }),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);
  const seen = [];
  el.addEventListener("input", () => seen.push(el.value));

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });
  env.el("ai-polish-confirm").click();

  assert.deepEqual(seen, ["AAAXYZCCC"]);
});

test("加载中与失败态下点确认替换都不会改动正文", async () => {
  const pending = deferred();
  const env = harness({ post: () => pending.promise });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  const opening = env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });
  env.el("ai-polish-confirm").click();
  assert.equal(el.value, "AAABBBCCC");

  pending.reject(new Error("润色失败，请稍后重试"));
  await opening;
  env.el("ai-polish-confirm").click();

  assert.equal(el.value, "AAABBBCCC");
  assert.equal(env.toasts.length, 0);
});

// ---------- 关闭路径 ----------

const CLOSE_WAYS = {
  cancel: (env) => env.el("ai-polish-cancel").click(),
  close: (env) => env.el("ai-polish-close").click(),
  escape: (env) => env.doc.fire("keydown", { key: "Escape", preventDefault() {} }),
  mask: (env) =>
    env.el("ai-polish-mask").dispatch("click", { target: env.el("ai-polish-mask") }),
};

Object.keys(CLOSE_WAYS).forEach((way) => {
  test(`通过「${way}」关闭弹窗不会改动正文`, async () => {
    const env = harness({
      post: () => Promise.resolve({ text: "XYZ", simulated: false }),
    });
    const el = textarea(env.doc, "AAABBBCCC", 3, 6);

    await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });
    CLOSE_WAYS[way](env);

    assert.equal(el.value, "AAABBBCCC");
    assert.equal(env.el("ai-polish-mask").hidden, true);
    assert.equal(env.toasts.length, 0);
  });
});

test("关闭后焦点与选区还给编辑区", async () => {
  const env = harness({
    post: () => Promise.resolve({ text: "XYZ", simulated: false }),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });
  assert.equal(env.doc.activeElement.id, "ai-polish-close");

  CLOSE_WAYS.cancel(env);

  assert.equal(env.doc.activeElement, el);
  assert.equal(el.selectionStart, 3);
  assert.equal(el.selectionEnd, 6);
});

test("点弹窗内部不会误关闭", async () => {
  const env = harness({
    post: () => Promise.resolve({ text: "XYZ", simulated: false }),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });
  env.el("ai-polish-mask").dispatch("click", { target: env.el("ai-polish-modal") });

  assert.equal(env.el("ai-polish-mask").hidden, false);
});

test("Tab 在弹窗内循环，不会跑到弹窗外", async () => {
  const env = harness({
    post: () => Promise.resolve({ text: "XYZ", simulated: false }),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });

  env.doc.fire("keydown", { key: "Tab", shiftKey: false, preventDefault() {} });
  assert.equal(env.doc.activeElement.id, "ai-polish-cancel");

  env.doc.fire("keydown", { key: "Tab", shiftKey: false, preventDefault() {} });
  assert.equal(env.doc.activeElement.id, "ai-polish-confirm");

  env.doc.fire("keydown", { key: "Tab", shiftKey: false, preventDefault() {} });
  assert.equal(env.doc.activeElement.id, "ai-polish-close");
});

test("关闭后监听全部解绑，不会残留", async () => {
  const env = harness({
    post: () => Promise.resolve({ text: "XYZ", simulated: false }),
  });
  const el = textarea(env.doc, "AAABBBCCC", 3, 6);

  await env.AiPolish.open({ textarea: el, start: 3, end: 6, text: "BBB" });
  CLOSE_WAYS.cancel(env);

  assert.equal(countHandlers(env.doc, "keydown"), 0);
  assert.equal(countHandlers(env.el("ai-polish-mask"), "click"), 0);
  assert.equal(countHandlers(env.el("ai-polish-close"), "click"), 0);
  assert.equal(countHandlers(env.el("ai-polish-confirm"), "click"), 0);
  assert.equal(countHandlers(env.el("ai-polish-retry"), "click"), 0);
});
