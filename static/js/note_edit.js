/**
 * 写笔记 / 编辑笔记：工具栏、预览、保存草稿、发布。
 *
 * 工具栏的文本变换全部委托给 Editor（纯函数），这里只处理选区读写与请求。
 * 所有请求走 Api，错误文案只展示后端 message。
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const match = window.location.pathname.match(/^\/notes\/(\d+)\/edit$/);
    let noteId = match ? match[1] : null;

    const titleEl = document.getElementById("title");
    const tagsEl = document.getElementById("tags");
    const contentEl = document.getElementById("content");
    const previewEl = document.getElementById("preview");
    const previewBtn = document.getElementById("toggle-preview");
    const previewLabel = document.getElementById("preview-label");
    const toolbarEl = document.getElementById("toolbar");
    const imagePanel = document.getElementById("image-panel");
    const uploadBtn = document.getElementById("upload-image");
    const imageUrlEl = document.getElementById("image-url");
    const insertUrlBtn = document.getElementById("insert-image-url");
    const fileInput = document.getElementById("file-input");
    const saveBtn = document.getElementById("save-draft");
    const publishBtn = document.getElementById("publish");
    const ctxMenu = document.getElementById("ctx-menu");
    const ctxPolish = document.getElementById("ctx-ai-polish");

    // 点击工具栏或文件选择器会让 textarea 失焦，操作前先把选区记下来
    let selection = { start: 0, end: 0 };

    function rememberSelection() {
      selection = { start: contentEl.selectionStart, end: contentEl.selectionEnd };
    }

    ["keyup", "mouseup", "select", "blur", "input"].forEach(function (type) {
      contentEl.addEventListener(type, rememberSelection);
    });

    function applyResult(result) {
      contentEl.value = result.value;
      contentEl.focus();
      contentEl.setSelectionRange(result.start, result.end);
      selection = { start: result.start, end: result.end };
    }

    function insertImage(url, alt) {
      applyResult(
        window.Editor.insertImage(contentEl.value, selection.start, selection.end, url, alt)
      );
    }

    function runAction(action) {
      const value = contentEl.value;
      const start = selection.start;
      const end = selection.end;
      const Editor = window.Editor;

      switch (action) {
        case "bold":
          return applyResult(Editor.wrap(value, start, end, "**"));
        case "italic":
          return applyResult(Editor.wrap(value, start, end, "*"));
        case "code":
          return applyResult(Editor.wrap(value, start, end, "`"));
        case "h1":
          return applyResult(Editor.prefixLines(value, start, end, "# "));
        case "h2":
          return applyResult(Editor.prefixLines(value, start, end, "## "));
        case "quote":
          return applyResult(Editor.prefixLines(value, start, end, "> "));
        case "ul":
          return applyResult(Editor.prefixLines(value, start, end, "- "));
        case "ol":
          return applyResult(Editor.prefixLines(value, start, end, "1. "));
        case "link":
          return applyResult(Editor.insertLink(value, start, end));
        case "image":
          imagePanel.hidden = !imagePanel.hidden;
          if (!imagePanel.hidden) imageUrlEl.focus();
          return undefined;
        default:
          return undefined;
      }
    }

    // ---------- 右键上下文菜单：仅「AI 润色」一项，无选区时置灰 ----------

    function closeMenu(backToEditor) {
      if (ctxMenu.hidden) return;
      ctxMenu.hidden = true;
      if (backToEditor) {
        contentEl.focus();
        contentEl.setSelectionRange(selection.start, selection.end);
      }
    }

    function openMenu(x, y) {
      ctxPolish.disabled = !AiPolish.hasSelection(selection.start, selection.end);
      ctxMenu.hidden = false;

      const rect = ctxMenu.getBoundingClientRect();
      const pos = AiPolish.menuPosition(
        x,
        y,
        rect.width,
        rect.height,
        window.innerWidth,
        window.innerHeight
      );
      ctxMenu.style.left = pos.left + "px";
      ctxMenu.style.top = pos.top + "px";
      ctxPolish.focus();
    }

    contentEl.addEventListener("contextmenu", function (event) {
      event.preventDefault();
      rememberSelection();
      openMenu(event.clientX, event.clientY);
    });

    // Shift+F10 / 菜单键：键盘也能唤起菜单
    contentEl.addEventListener("keydown", function (event) {
      if (!AiPolish.isMenuKey(event)) return;
      event.preventDefault();
      const rect = contentEl.getBoundingClientRect();
      openMenu(rect.left + rect.width / 2, rect.top + rect.height / 2);
    });

    // Esc 关闭菜单：焦点可能在编辑区（菜单项置灰时无法聚焦），所以挂到 document
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || ctxMenu.hidden) return;
      closeMenu(true);
    });

    ctxPolish.addEventListener("click", function () {
      if (ctxPolish.disabled) return;
      const start = selection.start;
      const end = selection.end;
      closeMenu(false);
      AiPolish.open({
        textarea: contentEl,
        start: start,
        end: end,
        text: contentEl.value.slice(start, end),
      });
    });

    document.addEventListener("click", function (event) {
      if (ctxMenu.hidden || ctxMenu.contains(event.target)) return;
      closeMenu(false);
    });

    window.addEventListener("scroll", function () {
      closeMenu(false);
    }, true);

    window.addEventListener("resize", function () {
      closeMenu(false);
    });

    toolbarEl.addEventListener("click", function (event) {
      const button = event.target.closest("[data-action]");
      if (!button) return;
      runAction(button.dataset.action);
    });

    uploadBtn.addEventListener("click", function () {
      fileInput.click();
    });

    fileInput.addEventListener("change", function () {
      const file = fileInput.files[0];
      if (!file) return;

      const form = new FormData();
      form.append("file", file);
      uploadBtn.disabled = true;

      Api.upload("/api/upload", form)
        .then(function (data) {
          imagePanel.hidden = true;
          insertImage(data.url, "");
        })
        .catch(function () {})
        .then(function () {
          uploadBtn.disabled = false;
          fileInput.value = "";
        });
    });

    insertUrlBtn.addEventListener("click", function () {
      const url = imageUrlEl.value.trim();
      if (!url) return;
      imagePanel.hidden = true;
      insertImage(url, "图片");
      imageUrlEl.value = "";
    });

    function setPreview(on) {
      previewBtn.setAttribute("aria-pressed", on ? "true" : "false");
      previewLabel.textContent = on ? "编辑" : "预览";
      // 渲染结果已经过 renderMarkdown 消毒，可直接插入
      previewEl.innerHTML = on ? window.renderMarkdown(contentEl.value) : "";
      previewEl.hidden = !on;
      contentEl.hidden = on;
    }

    previewBtn.addEventListener("click", function () {
      setPreview(previewEl.hidden);
    });

    function payload(status) {
      return {
        title: titleEl.value,
        content: contentEl.value,
        tags: tagsEl.value,
        status: status,
      };
    }

    function submit(status) {
      saveBtn.disabled = true;
      publishBtn.disabled = true;

      const request = noteId
        ? Api.put("/api/notes/" + noteId, payload(status))
        : Api.post("/api/notes", payload(status));

      return request
        .then(function (data) {
          if (status === "published") {
            window.location.href = "/notes/" + data.id;
            return;
          }
          Toast.show("草稿已保存", "success");
          if (!noteId) {
            // 保存后留在当前页继续编辑，地址切换为编辑态
            noteId = data.id;
            window.history.replaceState(null, "", "/notes/" + noteId + "/edit");
          }
        })
        .catch(function () {})
        .then(function () {
          saveBtn.disabled = false;
          publishBtn.disabled = false;
        });
    }

    saveBtn.addEventListener("click", function () {
      submit("draft");
    });

    publishBtn.addEventListener("click", function () {
      submit("published");
    });

    if (noteId) {
      Api.get("/api/notes/" + noteId)
        .then(function (data) {
          const note = data.note;
          titleEl.value = note.title;
          tagsEl.value = (note.tags || []).join(",");
          contentEl.value = note.content;
        })
        .catch(function () {});
    }
  });
})();
