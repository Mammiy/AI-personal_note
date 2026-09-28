/**
 * share.js 中的纯函数测试（Node 内置 test runner，零依赖）。
 * 运行：node --test tests/js/share.test.js
 *
 * 分享页四种状态由接口 code 决定，状态映射抽成纯函数以便自动化验证。
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const TARGET = path.join(__dirname, "..", "..", "static", "js", "share.js");

function loadSharePage() {
  const sandbox = { console, JSON, String };
  sandbox.window = {};
  sandbox.document = { addEventListener: () => {} };
  sandbox.Api = {};
  sandbox.Toast = { show: () => {} };
  const context = vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(TARGET, "utf8"), context, {
    filename: "share.js",
  });
  return sandbox.window.SharePage;
}

const SharePage = loadSharePage();

test("分享关闭进入关闭态", () => {
  assert.equal(SharePage.stateOfCode("SHARE_CLOSED"), "closed");
});

test("需要密码进入密码门", () => {
  assert.equal(SharePage.stateOfCode("SHARE_PASSWORD_REQUIRED"), "gate");
});

test("密码错误停留在密码门可重试", () => {
  assert.equal(SharePage.stateOfCode("SHARE_PASSWORD_WRONG"), "gate");
});

test("未识别的错误一律按关闭态处理，不泄露笔记是否存在", () => {
  assert.equal(SharePage.stateOfCode("SERVER_ERROR"), "closed");
  assert.equal(SharePage.stateOfCode(undefined), "closed");
});
