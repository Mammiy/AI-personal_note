/**
 * 个人主页：个人信息只读、我的收藏列表、笔记版本历史（只读，不提供恢复入口）。
 */
(function () {
  const Profile = {
    /** 空态文案：区分「没有笔记可选」与「该笔记还没有版本」 */
    versionEmptyText: function (hasNote) {
      return hasNote ? "这篇笔记还没有版本记录" : "还没有版本记录";
    },
  };
  window.Profile = Profile;

  document.addEventListener("DOMContentLoaded", function () {
    const usernameEl = document.getElementById("profile-username");
    const emailEl = document.getElementById("profile-email");
    const createdEl = document.getElementById("profile-created");

    const favList = document.getElementById("fav-list");
    const favEmpty = document.getElementById("fav-empty");

    const noteSelect = document.getElementById("note-select");
    const versionList = document.getElementById("version-list");
    const versionEmpty = document.getElementById("version-empty");
    const versionView = document.getElementById("version-view");
    const versionTitle = document.getElementById("version-title");
    const versionMeta = document.getElementById("version-meta");
    const versionContent = document.getElementById("version-content");

    function favoriteNode(item) {
      const li = document.createElement("li");
      li.className = "fav-row";

      const link = document.createElement("a");
      link.className = "fav-row__title";
      link.href = "/notes/" + item.note_id;
      link.textContent = item.title;
      li.appendChild(link);

      const meta = document.createElement("span");
      meta.className = "fav-row__meta";
      meta.textContent = "收藏于 " + item.favorited_at;
      li.appendChild(meta);
      return li;
    }

    function renderFavorites(items) {
      favList.textContent = "";
      items.forEach(function (item) {
        favList.appendChild(favoriteNode(item));
      });
      favEmpty.hidden = items.length > 0;
    }

    function renderNoteOptions(notes) {
      notes.forEach(function (note) {
        const option = document.createElement("option");
        option.value = String(note.id);
        option.textContent = note.title;
        noteSelect.appendChild(option);
      });
    }

    function versionNode(noteId, item) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "version-row";
      btn.innerHTML =
        '<span class="version-row__title"></span><span class="version-row__time"></span>';
      btn.querySelector(".version-row__title").textContent = item.title;
      btn.querySelector(".version-row__time").textContent = item.created_at;
      btn.addEventListener("click", function () {
        showVersion(noteId, item.id);
      });
      li.appendChild(btn);
      return li;
    }

    function showVersion(noteId, versionId) {
      Api.get("/api/notes/" + noteId + "/versions/" + versionId)
        .then(function (data) {
          versionTitle.textContent = data.title;
          versionMeta.textContent = "";

          (data.tags || []).forEach(function (tag) {
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.textContent = tag;
            versionMeta.appendChild(chip);
          });

          const time = document.createElement("span");
          time.className = "note-meta__item";
          time.textContent = "保存于 " + data.created_at;
          versionMeta.appendChild(time);

          versionContent.innerHTML = window.renderMarkdown(data.content);
          versionView.hidden = false;
        })
        .catch(function () {
          versionView.hidden = true;
        });
    }

    function loadVersions(noteId) {
      versionView.hidden = true;
      versionList.textContent = "";

      if (!noteId) {
        versionEmpty.textContent = Profile.versionEmptyText(false);
        versionEmpty.hidden = false;
        return;
      }

      Api.get("/api/notes/" + noteId + "/versions")
        .then(function (data) {
          versionEmpty.textContent = Profile.versionEmptyText(true);
          versionEmpty.hidden = data.items.length > 0;
          data.items.forEach(function (item) {
            versionList.appendChild(versionNode(noteId, item));
          });
        })
        .catch(function () {
          versionEmpty.textContent = Profile.versionEmptyText(true);
          versionEmpty.hidden = false;
        });
    }

    noteSelect.addEventListener("change", function () {
      loadVersions(noteSelect.value);
    });

    Api.get("/api/profile")
      .then(function (data) {
        usernameEl.textContent = data.user.username;
        emailEl.textContent = data.user.email;
        createdEl.textContent = data.user.created_at;

        renderFavorites(data.favorites || []);
        renderNoteOptions(data.notes || []);
        loadVersions("");
      })
      .catch(function () {});
  });
})();
