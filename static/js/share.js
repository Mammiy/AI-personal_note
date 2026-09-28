/**
 * 分享页：按接口返回的 code 在四种状态间切换（分享关闭 / 待输密码 / 密码错误 / 正常阅读）。
 * 页面骨架不含任何笔记内容，未通过验证前不渲染标题与正文。
 */
(function () {
  const SharePage = {
    /** 分享页错误码 → 状态名，便于纯函数测试。 */
    commentStateText: function (enabled) {
      return enabled ? "评论已开启" : "评论已关闭";
    },
    commentCountText: function (count) {
      return "(" + count + ")";
    },
    stateOfCode: function (code) {
      if (code === "SHARE_CLOSED") return "closed";
      // 密码错误仍停留在密码门，只是多一条错误提示
      if (code === "SHARE_PASSWORD_REQUIRED" || code === "SHARE_PASSWORD_WRONG") return "gate";
      return "closed";
    },
  };
  window.SharePage = SharePage;

  document.addEventListener("DOMContentLoaded", function () {
    const token = window.SHARE_TOKEN;

    const headingEl = document.getElementById("share-heading");
    const gateEl = document.getElementById("share-gate-card");
    const readEl = document.getElementById("share-read");
    const metaEl = document.getElementById("share-meta");
    const contentEl = document.getElementById("share-content");
    const passwordEl = document.getElementById("share-password");
    const verifyBtn = document.getElementById("share-verify-btn");
    const errorEl = document.getElementById("share-gate-error");

    const commentCard = document.getElementById("share-comment-card");
    const commentCount = document.getElementById("share-comment-count");
    const commentList = document.getElementById("share-comment-list");
    const commentForm = document.getElementById("share-comment-form");
    const guestNameEl = document.getElementById("share-guest-name");
    const commentInputEl = document.getElementById("share-comment-input");
    const commentSubmitBtn = document.getElementById("share-comment-submit");

    // 缓存后端下发的密码门提示，密码错误时标题不跟着变
    let gateHint = "";

    /** 关闭态：只留一条软提示，不渲染任何笔记信息 */
    function showClosed(text) {
      headingEl.textContent = text;
      headingEl.classList.add("share-heading--muted");
      gateEl.hidden = true;
      readEl.hidden = true;
      commentCard.hidden = true;
    }

    function showGate(hint, errorText) {
      // 提示文案取后端 message，前端不硬编码业务错误文案
      headingEl.textContent = hint || "该笔记需要密码才能查看";
      headingEl.classList.add("share-heading--muted");
      errorEl.textContent = errorText || "";
      readEl.hidden = true;
      gateEl.hidden = false;
      commentCard.hidden = true;
      passwordEl.focus();
    }

    function showGateError(message) {
      errorEl.textContent = message;
      passwordEl.select();
      passwordEl.focus();
    }

    function render(data) {
      headingEl.textContent = data.title;
      headingEl.classList.remove("share-heading--muted");
      metaEl.textContent = "更新: " + data.updated_at;
      contentEl.innerHTML = window.renderMarkdown(data.content);
      gateEl.hidden = true;
      readEl.hidden = false;
      document.title = data.title + " · 个人笔记";
    }

    // ---------- 访客评论 ----------

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

      const body = document.createElement("p");
      body.className = "comment__content";
      body.textContent = item.content;

      li.appendChild(head);
      li.appendChild(body);
      return li;
    }

    function loadComments() {
      Api.get("/api/share/" + token + "/comments")
        .then(function (data) {
          const enabled = !!data.enabled;
          commentCard.hidden = false;
          commentCount.textContent = SharePage.commentCountText(data.items.length);

          commentList.textContent = "";
          if (!enabled) {
            commentList.appendChild(emptyNode("评论已关闭"));
          } else if (data.items.length === 0) {
            commentList.appendChild(emptyNode("还没有评论，来说点什么吧"));
          } else {
            data.items.forEach(function (item) {
              commentList.appendChild(commentNode(item));
            });
          }
          commentForm.hidden = !enabled;
        })
        .catch(function () {});
    }

    function emptyNode(text) {
      const li = document.createElement("li");
      li.className = "comment comment--empty";
      li.textContent = text;
      return li;
    }

    function submitComment() {
      const content = commentInputEl.value.trim();
      const guestName = guestNameEl.value.trim();
      if (!content) {
        Toast.show("请输入评论内容");
        return;
      }
      if (!guestName) {
        Toast.show("请填写 1 到 20 个字符的昵称");
        return;
      }
      commentSubmitBtn.disabled = true;
      Api.post("/api/share/" + token + "/comments", { content: content, guest_name: guestName })
        .then(function () {
          commentInputEl.value = "";
          Toast.show("评论已发布", "success");
        })
        .catch(function () {})
        .then(function () {
          commentSubmitBtn.disabled = false;
          loadComments();
        });
    }

    function load() {
      return Api.get("/api/share/" + token)
        .then(function (data) {
          render(data);
          loadComments();
        })
        .catch(function (err) {
          const state = SharePage.stateOfCode(err && err.code);
          if (state === "gate") {
            if (err && err.code === "SHARE_PASSWORD_WRONG") {
              showGate(gateHint, err.message);
            } else {
              gateHint = (err && err.message) || gateHint;
              showGate(gateHint, "");
            }
          } else {
            // 分享关闭与未知错误一律只给「分享已关闭」，不泄露笔记是否存在
            showClosed(state === "closed" && err && err.message ? err.message : "分享已关闭");
          }
        });
    }

    function verify() {
      const password = passwordEl.value;
      verifyBtn.disabled = true;
      Api.post("/api/share/" + token + "/verify", { password: password })
        .then(function () {
          errorEl.textContent = "";
          passwordEl.value = "";
          return load();
        })
        .catch(function (err) {
          // 密码错误只提示，输入框内容保留便于重试
          showGateError((err && err.message) || "密码错误，请重新输入");
        })
        .then(function () {
          verifyBtn.disabled = false;
        });
    }

    verifyBtn.addEventListener("click", verify);
    commentSubmitBtn.addEventListener("click", submitComment);
    passwordEl.addEventListener("keydown", function (event) {
      if (event.key === "Enter") verify();
    });

    load();
  });
})();
