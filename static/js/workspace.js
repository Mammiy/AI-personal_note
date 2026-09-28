/**
 * 工作台：拉取统计与最近文章并渲染。
 * 失败提示由 Api 统一弹出（只展示后端 message），这里只负责回到空态。
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const listEl = document.getElementById("recent-list");
    const emptyEl = document.getElementById("recent-empty");

    function rowEl(item) {
      const row = document.createElement("a");
      row.className = "note-row";
      row.href = "/notes/" + item.id;

      const title = document.createElement("span");
      title.className = "note-row__title";
      title.textContent = item.title;

      const meta = document.createElement("span");
      meta.className = "note-row__meta";

      const status = document.createElement("span");
      status.className = item.status === "published" ? "chip chip--success" : "chip";
      status.textContent = item.status === "published" ? "已发布" : "草稿";

      const time = document.createElement("span");
      time.className = "note-row__time";
      time.textContent = item.updated_at;

      meta.appendChild(status);
      meta.appendChild(time);
      row.appendChild(title);
      row.appendChild(meta);
      return row;
    }

    function render(data) {
      document.getElementById("stat-draft").textContent = data.draft_count;
      document.getElementById("stat-published").textContent = data.published_count;
      document.getElementById("stat-favorite").textContent = data.favorite_count;

      listEl.textContent = "";
      data.recent.forEach(function (item) {
        listEl.appendChild(rowEl(item));
      });
      emptyEl.hidden = data.recent.length !== 0;
    }

    Api.get("/api/workspace/summary")
      .then(render)
      .catch(function () {
        listEl.textContent = "";
        emptyEl.hidden = false;
      });
  });
})();
