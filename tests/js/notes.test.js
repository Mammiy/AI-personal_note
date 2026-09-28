/**
 * notes.js 中的纯函数测试（Node 内置 test runner，零依赖）。
 * 运行：node --test tests/js/notes.test.js
 *
 * 筛选与空态文案都是纯函数，DOM 相关代码只在 DOMContentLoaded 后执行，
 * 因此在 Node 里加载该文件不会触碰 DOM。
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const NOTES_PATH = path.join(__dirname, "..", "..", "static", "js", "notes.js");

function loadNoteList() {
  const sandbox = { console, JSON, String, Array, Object };
  sandbox.window = {};
  sandbox.document = { addEventListener: () => {} };
  sandbox.Api = {};
  sandbox.Toast = { show: () => {} };
  const context = vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(NOTES_PATH, "utf8"), context, {
    filename: "notes.js",
  });
  return sandbox.window.NoteList;
}

const NoteList = loadNoteList();

const ITEMS = [
  { id: 1, title: "读书笔记", content: "读了孙子兵法", tags: ["生活", "随笔"], status: "draft" },
  { id: 2, title: "旅行计划", content: "想去大理", tags: ["生活"], status: "draft" },
  { id: 3, title: "工作复盘", content: "本周完成了重构", tags: ["工作"], status: "published" },
];

// ---------- 筛选 ----------

test("无条件时返回全部笔记", () => {
  assert.deepEqual(
    NoteList.filterNotes(ITEMS, {}).map((item) => item.id),
    [1, 2, 3]
  );
});

test("关键词命中标题", () => {
  const result = NoteList.filterNotes(ITEMS, { keyword: "旅行" });

  assert.deepEqual(result.map((item) => item.id), [2]);
});

test("关键词命中正文", () => {
  const result = NoteList.filterNotes(ITEMS, { keyword: "大理" });

  assert.deepEqual(result.map((item) => item.id), [2]);
});

test("关键词忽略首尾空格", () => {
  const result = NoteList.filterNotes(ITEMS, { keyword: "  旅行  " });

  assert.deepEqual(result.map((item) => item.id), [2]);
});

test("状态筛选只保留草稿", () => {
  const result = NoteList.filterNotes(ITEMS, { status: "draft" });

  assert.deepEqual(result.map((item) => item.id), [1, 2]);
});

test("状态筛选只保留已发布", () => {
  const result = NoteList.filterNotes(ITEMS, { status: "published" });

  assert.deepEqual(result.map((item) => item.id), [3]);
});

test("多标签按任意命中过滤", () => {
  const result = NoteList.filterNotes(ITEMS, { tags: ["随笔", "工作"] });

  assert.deepEqual(result.map((item) => item.id), [1, 3]);
});

test("关键词、标签、状态三者叠加", () => {
  const hit = NoteList.filterNotes(ITEMS, {
    keyword: "复盘",
    tags: ["工作"],
    status: "published",
  });
  const miss = NoteList.filterNotes(ITEMS, {
    keyword: "复盘",
    tags: ["工作"],
    status: "draft",
  });

  assert.deepEqual(hit.map((item) => item.id), [3]);
  assert.deepEqual(miss, []);
});

test("筛选不修改原始数据", () => {
  NoteList.filterNotes(ITEMS, { keyword: "复盘", status: "published" });

  assert.equal(ITEMS.length, 3);
});

// ---------- 空态与筛选计数 ----------

test("没有笔记时提示还没有任何笔记", () => {
  assert.equal(NoteList.emptyMessage(0), "还没有任何笔记");
});

test("有笔记但没命中时引导换关键词", () => {
  assert.equal(
    NoteList.emptyMessage(3),
    "没有找到匹配的笔记，换个关键词试试"
  );
});

test("筛选条件数量按关键词、标签组、状态分别计数", () => {
  assert.equal(NoteList.activeFilterCount({}), 0);
  assert.equal(NoteList.activeFilterCount({ keyword: "旅行" }), 1);
  assert.equal(NoteList.activeFilterCount({ tags: ["生活", "工作"] }), 1);
  assert.equal(NoteList.activeFilterCount({ status: "draft" }), 1);
  assert.equal(
    NoteList.activeFilterCount({ keyword: "旅行", tags: ["生活"], status: "draft" }),
    3
  );
});
