/**
 * api.js 行为测试（Node 内置 test runner，零依赖）。
 * 运行：node --test tests/js/api.test.js
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const API_PATH = path.join(__dirname, "..", "..", "static", "js", "api.js");

/** 在受控沙箱里加载 api.js，注入 fetch / Toast / 定时器替身 */
function loadApi({ response, toast }) {
  const toastCalls = [];
  const timers = [];
  const fetchCalls = [];

  const sandbox = {
    JSON,
    Error,
    console,
    setTimeout: (fn, delay) => {
      timers.push({ fn, delay });
      return timers.length;
    },
    clearTimeout: () => {},
    Toast: {
      show: (message, type) => {
        toastCalls.push({ message, type });
        if (toast) toast(message, type);
      },
    },
    window: { location: { href: "/" } },
    fetch: async (url, opts) => {
      fetchCalls.push({ url, opts });
      return response;
    },
  };

  const context = vm.createContext(sandbox);
  vm.runInContext(
    fs.readFileSync(API_PATH, "utf8") + "\nglobalThis.Api = Api;",
    context,
    { filename: "api.js" }
  );

  return { Api: sandbox.Api, toastCalls, timers, fetchCalls, win: sandbox.window };
}

function jsonResponse(payload) {
  return { json: async () => payload };
}

test("code 为 OK 时返回 data", async () => {
  const { Api } = loadApi({ response: jsonResponse({ code: "OK", message: "操作成功", data: { status: "up" } }) });

  const data = await Api.get("/api/health");
  assert.deepEqual(data, { status: "up" });
});

test("POST 以 JSON 发送且携带同源凭证", async () => {
  const { Api, fetchCalls } = loadApi({ response: jsonResponse({ code: "OK", message: "操作成功", data: null }) });

  await Api.post("/api/auth/login", { email: "a@b.com", password: "secret" });

  const call = fetchCalls[0];
  assert.equal(call.url, "/api/auth/login");
  assert.equal(call.opts.method, "POST");
  assert.equal(call.opts.credentials, "same-origin");
  assert.equal(call.opts.headers["Content-Type"], "application/json");
  assert.equal(call.opts.body, JSON.stringify({ email: "a@b.com", password: "secret" }));
});

test("业务失败时展示后端 message 并抛出带 code 的错误", async () => {
  const { Api, toastCalls } = loadApi({
    response: jsonResponse({ code: "CONFLICT", message: "该邮箱已被注册", data: null }),
  });

  await assert.rejects(
    () => Api.post("/api/auth/register", {}),
    (err) => err.code === "CONFLICT" && err.message === "该邮箱已被注册"
  );
  assert.deepEqual(toastCalls, [{ message: "该邮箱已被注册", type: undefined }]);
});

test("未授权时提示并在 800ms 后跳转登录页", async () => {
  const { Api, toastCalls, timers, win } = loadApi({
    response: jsonResponse({ code: "UNAUTHORIZED", message: "请先登录", data: null }),
  });

  await assert.rejects(() => Api.get("/api/auth/me"), /请先登录/);

  assert.deepEqual(toastCalls, [{ message: "请先登录", type: undefined }]);
  assert.equal(timers.length, 1);
  assert.equal(timers[0].delay, 800);
  timers[0].fn();
  assert.equal(win.location.href, "/login");
});

test("响应不是 JSON 时提示服务器繁忙", async () => {
  const { Api, toastCalls } = loadApi({
    response: { json: async () => { throw new Error("not json"); } },
  });

  await assert.rejects(() => Api.get("/api/health"));
  assert.deepEqual(toastCalls, [{ message: "服务器繁忙，请稍后重试", type: undefined }]);
});

test("上传走表单体且不设置 JSON 头", async () => {
  const { Api, fetchCalls } = loadApi({ response: jsonResponse({ code: "OK", message: "操作成功", data: { url: "/u/1.png" } }) });

  const form = { marker: "formdata" };
  await Api.upload("/api/upload", form);

  const call = fetchCalls[0];
  assert.equal(call.opts.method, "POST");
  assert.equal(call.opts.body, form);
  assert.equal(call.opts.headers["Content-Type"], undefined);
});
