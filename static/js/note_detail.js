/**
 * 笔记详情：渲染标题、元信息与正文，绑定编辑、删除与分享设置卡片。
 * 正文渲染复用 renderMarkdown（已消毒），与编辑页预览保持一致。
 */
(function () {
  // 与 icons.html 中 trash 图标保持一致，动态节点无法走 Jinja 宏
  var TRASH_SVG =
    '<svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<path d="M4 7h16"/><path d="M9 7V5h6v2"/><path d="M6 7l1 13h10l1-13"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>';

  // 与 icons.html 中 heart 图标一致：未收藏描边、已收藏实底
  var HEART_PATH = '<path d="M12 20s-7-4.4-7-9a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 4.6-7 9-7 9Z"/>';

  function heartSvg(filled) {
    return (
      '<svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="' +
      (filled ? "currentColor" : "none") +
      '" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" ' +
      'aria-hidden="true" focusable="false">' +
      HEART_PATH +
      "</svg>"
    );
  }

  /** 纯函数集合：不触碰 DOM，便于在 Node 里直接断言。 */
  const NoteDetail = {
    /** 相对分享路径拼成完整链接，供只读输入框与复制使用。 */
    fullLink: function (origin, shareUrl) {
      if (!shareUrl) return "";
      return String(origin).replace(/\/+$/, "") + shareUrl;
    },
    shareStateText: function (isShared) {
      return isShared ? "分享已开启" : "分享已关闭";
    },
    commentStateText: function (enabled) {
      return enabled ? "评论已开启" : "评论已关闭";
    },
    commentCountText: function (count) {
      return "(" + count + ")";
    },
    favoriteToast: function (on) {
      return on ? "已收藏" : "已取消收藏";
    },
    favoriteLabel: function (on) {
      return on ? "取消收藏" : "收藏";
    },
  };
  window.NoteDetail = NoteDetail;

  document.addEventListener("DOMContentLoaded", function () {
    const noteId = window.location.pathname.split("/")[2];

    const titleEl = document.getElementById("note-title");
    const metaEl = document.getElementById("note-meta");
    const contentEl = document.getElementById("note-content");
    const editBtn = document.getElementById("edit-btn");
    const deleteBtn = document.getElementById("delete-btn");

    const shareCard = document.getElementById("share-card");
    const shareBody = document.getElementById("share-body");
    const shareToggle = document.getElementById("share-toggle");
    const shareSwitch = document.getElementById("share-switch");
    const shareState = document.getElementById("share-state");
    const shareLinkInput = document.getElementById("share-link-input");
    const copyLinkBtn = document.getElementById("copy-link-btn");
    const passwordInput = document.getElementById("share-password-input");
    const savePasswordBtn = document.getElementById("save-password-btn");

    const commentCard = document.getElementById("comment-card");
    const commentCount = document.getElementById("comment-count");
    const commentState = document.getElementById("comment-state");
    const commentSwitch = document.getElementById("comment-switch");
    const commentList = document.getElementById("comment-list");
    const commentForm = document.getElementById("comment-form");
    const commentInput = document.getElementById("comment-input");
    const commentSubmitBtn = document.getElementById("comment-submit-btn");

    const favoriteBtn = document.getElementById("favorite-btn");
    const favoriteIcon = document.getElementById("favorite-icon");

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

    /** 按接口返回刷新开关、状态文案与只读链接。 */
    function applyShare(data) {
      const isShared = !!data.is_shared;
      shareSwitch.setAttribute("aria-checked", isShared ? "true" : "false");
      shareState.textContent = NoteDetail.shareStateText(isShared);
      shareLinkInput.value = isShared ? NoteDetail.fullLink(window.location.origin, data.share_url) : "";
    }

    function toggleShare() {
      const next = shareSwitch.getAttribute("aria-checked") !== "true";
      shareSwitch.disabled = true;
      Api.put("/api/notes/" + noteId + "/share", { is_shared: next })
        .then(function (data) {
          applyShare(data);
          Toast.show(NoteDetail.shareStateText(next), "success");
        })
        .catch(function () {})
        .then(function () {
          shareSwitch.disabled = false;
        });
    }

    function savePassword() {
      savePasswordBtn.disabled = true;
      // 只改密码，不带偏分享开关的当前状态
      const isShared = shareSwitch.getAttribute("aria-checked") === "true";
      Api.put("/api/notes/" + noteId + "/share", { is_shared: isShared, password: passwordInput.value })
        .then(function (data) {
          applyShare(data);
          passwordInput.value = "";
          Toast.show("密码已保存", "success");
        })
        .catch(function () {})
        .then(function () {
          savePasswordBtn.disabled = false;
        });
    }

    function toggleShareCard() {
      const expanded = shareToggle.getAttribute("aria-expanded") === "true";
      shareToggle.setAttribute("aria-expanded", expanded ? "false" : "true");
      shareToggle.textContent = expanded ? "展开" : "收起";
      shareBody.hidden = expanded;
    }

    // ---------- 评论 ----------

    function commentNode(item) {
      const li = document.createElement("li");
      li.className = "comment";

      const head = document.createElement("div");
      head.className = "comment__head";

      const name = document.createElement("span");
      name.className = "comment__name";
      name.textContent = item.display_name;
      head.appendChild(name);

      if (item.is_guest) {
        const badge = document.createElement("span");
        badge.className = "chip";
        badge.textContent = "访客";
        head.appendChild(badge);
      }

      const time = document.createElement("span");
      time.className = "comment__time";
      time.textContent = item.created_at;
      head.appendChild(time);

      if (item.can_delete) {
        const del = document.createElement("button");
        del.type = "button";
        del.className = "btn btn--text btn--danger-text";
        del.innerHTML = TRASH_SVG + "删除";
        del.addEventListener("click", function () {
          UI.confirm("确定删除这条评论吗？").then(function (confirmed) {
            if (!confirmed) return;
            Api.del("/api/comments/" + item.id)
              .then(function () {
                Toast.show("评论已删除", "success");
              })
              .catch(function () {})
              .then(loadComments);
          });
        });
        head.appendChild(del);
      }

      const body = document.createElement("p");
      body.className = "comment__content";
      body.textContent = item.content;

      li.appendChild(head);
      li.appendChild(body);
      return li;
    }

    function emptyCommentNode(text) {
      const li = document.createElement("li");
      li.className = "comment comment--empty";
      li.textContent = text;
      return li;
    }

    function loadComments() {
      Api.get("/api/notes/" + noteId + "/comments")
        .then(function (data) {
          const enabled = !!data.enabled;
          commentCard.hidden = false;
          commentSwitch.setAttribute("aria-checked", enabled ? "true" : "false");
          commentState.textContent = NoteDetail.commentStateText(enabled);
          commentCount.textContent = NoteDetail.commentCountText(data.items.length);

          commentList.textContent = "";
          if (!enabled) {
            commentList.appendChild(emptyCommentNode("评论已关闭"));
          } else if (data.items.length === 0) {
            commentList.appendChild(emptyCommentNode("还没有评论，来说点什么吧"));
          } else {
            data.items.forEach(function (item) {
              commentList.appendChild(commentNode(item));
            });
          }
          commentForm.hidden = !enabled;
        })
        .catch(function () {});
    }

    function submitComment() {
      const content = commentInput.value.trim();
      if (!content) {
        Toast.show("请输入评论内容");
        return;
      }
      commentSubmitBtn.disabled = true;
      Api.post("/api/notes/" + noteId + "/comments", { content: content })
        .then(function () {
          commentInput.value = "";
          Toast.show("评论已发布", "success");
        })
        .catch(function () {})
        .then(function () {
          commentSubmitBtn.disabled = false;
          loadComments();
        });
    }

    function toggleComments() {
      const next = commentSwitch.getAttribute("aria-checked") !== "true";
      commentSwitch.disabled = true;
      Api.put("/api/notes/" + noteId + "/comments/enabled", { enabled: next })
        .then(function () {
          Toast.show(NoteDetail.commentStateText(next), "success");
        })
        .catch(function () {})
        .then(function () {
          commentSwitch.disabled = false;
          loadComments();
        });
    }

    // ---------- 收藏 ----------

    function applyFavorite(on) {
      favoriteBtn.setAttribute("aria-pressed", on ? "true" : "false");
      favoriteBtn.classList.toggle("icon-btn--active", !!on);
      favoriteBtn.setAttribute("aria-label", NoteDetail.favoriteLabel(on));
      favoriteBtn.title = NoteDetail.favoriteLabel(on);
      favoriteIcon.innerHTML = heartSvg(!!on);
    }

    function toggleFavorite() {
      const on = favoriteBtn.getAttribute("aria-pressed") !== "true";
      favoriteBtn.disabled = true;
      const request = on
        ? Api.post("/api/notes/" + noteId + "/favorite", {})
        : Api.del("/api/notes/" + noteId + "/favorite");

      request
        .then(function () {
          applyFavorite(on);
          Toast.show(NoteDetail.favoriteToast(on), "success");
        })
        .catch(function () {})
        .then(function () {
          favoriteBtn.disabled = false;
        });
    }

    shareSwitch.addEventListener("click", toggleShare);
    savePasswordBtn.addEventListener("click", savePassword);
    commentSwitch.addEventListener("click", toggleComments);
    commentSubmitBtn.addEventListener("click", submitComment);
    favoriteBtn.addEventListener("click", toggleFavorite);
    shareToggle.addEventListener("click", toggleShareCard);
    copyLinkBtn.addEventListener("click", function () {
      if (!shareLinkInput.value) {
        Toast.show("请先开启分享");
        return;
      }
      UI.copy(shareLinkInput.value);
    });

    Api.get("/api/notes/" + noteId)
      .then(function (data) {
        const note = data.note;
        titleEl.textContent = note.title;
        renderMeta(note);
        contentEl.innerHTML = window.renderMarkdown(note.content);
        editBtn.href = "/notes/" + noteId + "/edit";

        shareCard.hidden = false;
        applyShare({ is_shared: data.is_shared, share_url: data.share_url });
        applyFavorite(!!data.is_favorited);
        loadComments();
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
