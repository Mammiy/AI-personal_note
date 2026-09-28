/**
 * note_detail.js 中的纯函数测试（Node 内置 test runner，零依赖）。
 * 运行：node --test tests/js/note_detail.test.js
 *
 * DOM 相关代码只在 DOMContentLoaded 后执行，因此在 Node 里加载该文件不会触碰 DOM。
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const TARGET = path.join(__dirname, "..", "..", "static", "js", "note_detail.js");

function loadNoteDetail() {
  const sandbox = { console, JSON, String };
  sandbox.window = {};
  sandbox.document = { addEventListener: () => {} };
  sandbox.Api = {};
  sandbox.Toast = { show: () => {} };
  sandbox.UI = {};
  const context = vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(TARGET, "utf8"), context, {
    filename: "note_detail.js",
  });
  return sandbox.window.NoteDetail;
}

const NoteDetail = loadNoteDetail();

test("未开启分享时链接为空", () => {
  assert.equal(NoteDetail.fullLink("http://127.0.0.1:5000", ""), "");
});

test("相对分享路径拼成完整链接", () => {
  assert.equal(
    NoteDetail.fullLink("http://127.0.0.1:5000", "/s/abc"),
    "http://127.0.0.1:5000/s/abc"
  );
});

test("origin 自带尾斜杠时不会出现双斜杠", () => {
  assert.equal(
    NoteDetail.fullLink("http://127.0.0.1:5000/", "/s/abc"),
    "http://127.0.0.1:5000/s/abc"
  );
});

test("分享状态文案只有开启与关闭两种", () => {
  assert.equal(NoteDetail.shareStateText(true), "分享已开启");
  assert.equal(NoteDetail.shareStateText(false), "分享已关闭");
});

test("评论开关文案照抄文案规范", () => {
  assert.equal(NoteDetail.commentStateText(true), "评论已开启");
  assert.equal(NoteDetail.commentStateText(false), "评论已关闭");
});

test("评论数按括号包裹展示", () => {
  assert.equal(NoteDetail.commentCountText(0), "(0)");
  assert.equal(NoteDetail.commentCountText(3), "(3)");
});

test("收藏切换的 Toast 文案", () => {
  assert.equal(NoteDetail.favoriteToast(true), "已收藏");
  assert.equal(NoteDetail.favoriteToast(false), "已取消收藏");
});

test("收藏按钮的无障碍名称随状态变化", () => {
  assert.equal(NoteDetail.favoriteLabel(true), "取消收藏");
  assert.equal(NoteDetail.favoriteLabel(false), "收藏");
});
