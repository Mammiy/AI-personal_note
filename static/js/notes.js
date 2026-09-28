/**
 * 我的文章：列表渲染与前端即时筛选。
 *
 * 列表一次加载全部，搜索与筛选都在本地完成，输入时不重复请求。
 * 筛选逻辑是纯函数（window.NoteList），DOM 操作只在 DOMContentLoaded 之后执行。
 */
(function () {
  /** 关键词命中标题或正文，标签多选按任意命中，状态精确匹配，三者叠加 */
  function filterNotes(items, options) {
    const opts = options || {};
    const keyword = (opts.keyword || "").trim().toLowerCase();
    const tags = opts.tags || [];
    const status = opts.status || "";

    return items.filter((item) => {
      if (status && item.status !== status) return false;
      if (tags.length && !tags.some((tag) => (item.tags || []).includes(tag))) return false;
      if (keyword) {
        const haystack = (item.title + "\n" + item.content).toLowerCase();
        if (haystack.indexOf(keyword) === -1) return false;
      }
      return true;
    });
  }

  /** 空态文案：区分"一篇都没有"与"筛选没命中" */
  function emptyMessage(total) {
    return total === 0 ? "还没有任何笔记" : "没有找到匹配的笔记，换个关键词试试";
  }

  /** 生效的筛选条件数量：关键词、标签组、状态各计一项 */
  function activeFilterCount(options) {
    const opts = options || {};
    let count = 0;
    if ((opts.keyword || "").trim()) count += 1;
    if ((opts.tags || []).length) count += 1;
    if (opts.status) count += 1;
    return count;
  }

  window.NoteList = { filterNotes, emptyMessage, activeFilterCount };

  document.addEventListener("DOMContentLoaded", function () {
    const state = { items: [], tags: [], selectedTags: [], keyword: "", status: "" };

    const listEl = document.getElementById("note-list");
    const emptyEl = document.getElementById("empty-state");
    const emptyTextEl = document.getElementById("empty-text");
    const tagEl = document.getElementById("tag-filter");
    const statusEl = document.getElementById("status-filter");
    const keywordEl = document.getElementById("keyword");
    const countEl = document.getElementById("filter-count");
    const clearEl = document.getElementById("clear-filter");

    function renderTags(tags) {
      tagEl.textContent = "";
      if (!tags.length) {
        const hint = document.createElement("span");
        hint.className = "card__meta";
        hint.textContent = "暂无标签";
        tagEl.appendChild(hint);
        return;
      }
      tags.forEach(function (tag) {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip chip--button";
        chip.textContent = tag;
        chip.dataset.tag = tag;
        chip.addEventListener("click", function () {
          const index = state.selectedTags.indexOf(tag);
          if (index === -1) state.selectedTags.push(tag);
          else state.selectedTags.splice(index, 1);
          render();
        });
        tagEl.appendChild(chip);
      });
    }

    function syncChips() {
      Array.prototype.forEach.call(tagEl.children, function (chip) {
        chip.classList.toggle("is-active", state.selectedTags.indexOf(chip.dataset.tag) !== -1);
      });
      Array.prototype.forEach.call(statusEl.children, function (chip) {
        chip.classList.toggle("is-active", (chip.dataset.status || "") === state.status);
      });
    }

    function rowEl(item) {
      const row = document.createElement("a");
      row.className = "note-row";
      row.href = "/notes/" + item.id;

      const title = document.createElement("h2");
      title.className = "note-row__title";
      title.textContent = item.title;

      const meta = document.createElement("div");
      meta.className = "note-row__meta";

      const status = document.createElement("span");
      status.className = item.status === "published" ? "chip chip--success" : "chip";
      status.textContent = item.status === "published" ? "已发布" : "草稿";
      meta.appendChild(status);

      (item.tags || []).forEach(function (tag) {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = tag;
        meta.appendChild(chip);
      });

      const time = document.createElement("span");
      time.className = "note-row__time";
      time.textContent = "更新: " + item.updated_at;
      meta.appendChild(time);

      row.appendChild(title);
      row.appendChild(meta);
      return row;
    }

    function render() {
      syncChips();
      const total = state.items.length;
      const visible = window.NoteList.filterNotes(state.items, {
        keyword: state.keyword,
        tags: state.selectedTags,
        status: state.status,
      });

      listEl.textContent = "";
      visible.forEach(function (item) {
        listEl.appendChild(rowEl(item));
      });

      const count = window.NoteList.activeFilterCount({
        keyword: state.keyword,
        tags: state.selectedTags,
        status: state.status,
      });
      countEl.textContent = count ? "当前筛选：" + count + " 项" : "";
      clearEl.hidden = count === 0;

      emptyEl.hidden = visible.length !== 0;
      emptyTextEl.textContent = visible.length === 0 ? window.NoteList.emptyMessage(total) : "";
    }

    keywordEl.addEventListener("input", function () {
      state.keyword = keywordEl.value;
      render();
    });

    statusEl.addEventListener("click", function (event) {
      const chip = event.target.closest("[data-status]");
      if (!chip) return;
      state.status = chip.dataset.status || "";
      render();
    });

    clearEl.addEventListener("click", function () {
      state.keyword = "";
      state.selectedTags = [];
      state.status = "";
      keywordEl.value = "";
      render();
    });

    Api.get("/api/notes")
      .then(function (data) {
        state.items = data.items || [];
        state.tags = data.tags || [];
        renderTags(state.tags);
        render();
      })
      .catch(function () {
        // 错误提示由 Api 统一弹出，这里只清空加载态
        listEl.textContent = "";
        emptyEl.hidden = false;
        emptyTextEl.textContent = window.NoteList.emptyMessage(0);
      });
  });
})();
