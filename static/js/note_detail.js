/**
 * 笔记详情：渲染标题、元信息与正文，绑定编辑与删除。
 * 正文渲染复用 renderMarkdown（已消毒），与编辑页预览保持一致。
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const noteId = window.location.pathname.split("/")[2];

    const titleEl = document.getElementById("note-title");
    const metaEl = document.getElementById("note-meta");
    const contentEl = document.getElementById("note-content");
    const editBtn = document.getElementById("edit-btn");
    const deleteBtn = document.getElementById("delete-btn");

    function chip(text, success) {
      const node = document.createElement("span");
      node.className = success ? "chip chip--success" : "chip";
      node.textContent = text;
      return node;
    }

    function renderMeta(note) {
      metaEl.textContent = "";
      metaEl.appendChild(chip(note.status === "published" ? "已发布" : "草稿", note.status === "published"));

      (note.tags || []).forEach(function (tag) {
        metaEl.appendChild(chip(tag, false));
      });

      const created = document.createElement("span");
      created.className = "note-meta__item";
      created.textContent = "创建: " + note.created_at;

      const updated = document.createElement("span");
      updated.className = "note-meta__item";
      updated.textContent = "更新: " + note.updated_at;

      metaEl.appendChild(created);
      metaEl.appendChild(updated);
    }

    Api.get("/api/notes/" + noteId)
      .then(function (data) {
        const note = data.note;
        titleEl.textContent = note.title;
        renderMeta(note);
        contentEl.innerHTML = window.renderMarkdown(note.content);
        editBtn.href = "/notes/" + noteId + "/edit";
      })
      .catch(function () {
        contentEl.textContent = "";
      });

    deleteBtn.addEventListener("click", function () {
      UI.confirm("确定删除这篇笔记吗？删除后无法恢复").then(function (confirmed) {
        if (!confirmed) return;
        deleteBtn.disabled = true;
        Api.del("/api/notes/" + noteId)
          .then(function () {
            window.location.href = "/notes";
          })
          .catch(function () {
            deleteBtn.disabled = false;
          });
      });
    });
  });
})();
