/**
 * AI 润色弹窗 F11：左右对照、加载 / 成功 / 失败三态、确认替换回写选区。
 *
 * 文本变换与状态判定都是纯函数，挂在 window.AiPolish 上，便于在 Node 里直接断言；
 * DOM 只在 open() 被调用时才读取，文件加载阶段不碰 DOM。
 * 文案一律来自需求文档「文案规范」与后端 message，不在此处拼接业务错误。
 */
(function () {
  const ENDPOINT = "/api/ai/polish";
  const LOADING_TEXT = "润色中…";
  const BADGE_TEXT = "模拟结果";
  const SIMULATE_HINT = "尚未配置大模型，当前展示模拟润色结果";
  const REPLACED_TEXT = "已替换选中的文本";
  // Api 已提示过的兜底文案，与 api.js 保持一致
  const FALLBACK_ERROR = "润色失败，请稍后重试";

  // ---------- 纯函数 ----------

  /** 用润色结果替换原选区，其余内容一字不动，返回新正文与光标位置。 */
  function replaceSelection(value, start, end, result) {
    return {
      value: value.slice(0, start) + result + value.slice(end),
      caret: start + result.length,
    };
  }

  /** 无选区时右键菜单项要置灰。 */
  function hasSelection(start, end) {
    return typeof start === "number" && typeof end === "number" && end > start;
  }

  /** 菜单贴边时拉回视口，避免菜单被截断。 */
  function menuPosition(x, y, width, height, viewportWidth, viewportHeight) {
    return {
      left: Math.max(0, Math.min(x, viewportWidth - width)),
      top: Math.max(0, Math.min(y, viewportHeight - height)),
    };
  }

  /** Shift+F10 / 菜单键：键盘唤起右键菜单。 */
  function isMenuKey(event) {
    if (!event) return false;
    return event.key === "ContextMenu" || (event.key === "F10" && Boolean(event.shiftKey));
  }

  /** 焦点在弹窗内循环，index 为 -1（焦点不在弹窗内）时从头/尾进入。 */
  function nextFocusIndex(index, count, step) {
    if (count <= 0) return -1;
    if (index < 0) return step > 0 ? 0 : count - 1;
    return (index + step + count) % count;
  }

  function canConfirm(status) {
    return status === "success";
  }

  function badgeText(simulated) {
    return simulated ? BADGE_TEXT : "";
  }

  // ---------- 弹窗 ----------

  let current = null;

  function grab() {
    return {
      mask: document.getElementById("ai-polish-mask"),
      modal: document.getElementById("ai-polish-modal"),
      closeBtn: document.getElementById("ai-polish-close"),
      source: document.getElementById("ai-polish-source"),
      result: document.getElementById("ai-polish-result"),
      loading: document.getElementById("ai-polish-loading"),
      loadingText: document.getElementById("ai-polish-loading-text"),
      error: document.getElementById("ai-polish-error"),
      retry: document.getElementById("ai-polish-retry"),
      badge: document.getElementById("ai-polish-badge"),
      hint: document.getElementById("ai-polish-hint"),
      cancel: document.getElementById("ai-polish-cancel"),
      confirm: document.getElementById("ai-polish-confirm"),
    };
  }

  function focusables(els) {
    return [els.closeBtn, els.retry, els.cancel, els.confirm].filter(function (el) {
      return el && !el.hidden && !el.disabled;
    });
  }

  function focusFirst(els) {
    const list = focusables(els);
    if (list.length) list[0].focus();
  }

  function setLoading(els) {
    els.loading.hidden = false;
    els.loadingText.textContent = LOADING_TEXT;
    els.result.hidden = true;
    els.error.hidden = true;
    els.retry.hidden = true;
    els.confirm.disabled = true;
  }

  function showResult(state, data) {
    if (current !== state) return;

    state.status = "success";
    state.result = (data && data.text) || "";

    const els = state.els;
    els.loading.hidden = true;
    els.error.hidden = true;
    els.retry.hidden = true;
    els.result.hidden = false;
    els.result.value = state.result;

    const badge = badgeText(Boolean(data && data.simulated));
    els.badge.textContent = badge;
    els.badge.hidden = !badge;
    els.hint.textContent = badge ? SIMULATE_HINT : "";
    els.confirm.disabled = false;
  }

  function showError(state, err) {
    if (current !== state) return;

    state.status = "error";

    const els = state.els;
    els.loading.hidden = true;
    els.result.hidden = true;
    els.error.hidden = false;
    els.error.textContent = (err && err.message) || FALLBACK_ERROR;
    els.retry.hidden = false;
    els.confirm.disabled = true;
  }

  function request(state) {
    state.status = "loading";
    setLoading(state.els);

    return Api.post(ENDPOINT, { text: state.source })
      .then(function (data) {
        showResult(state, data);
      })
      .catch(function (err) {
        showError(state, err);
      });
  }

  function restoreFocus(state) {
    const el = state.textarea;
    if (!el) return;
    el.focus();
    el.setSelectionRange(state.start, state.end);
  }

  function confirmReplace(state) {
    if (!canConfirm(state.status) || state.applied) return;

    state.applied = true;
    state.els.confirm.disabled = true;

    const el = state.textarea;
    const next = replaceSelection(el.value, state.start, state.end, state.result);
    el.value = next.value;
    el.focus();
    el.setSelectionRange(next.caret, next.caret);
    // 触发一次 input，预览与保存逻辑拿到最新内容
    el.dispatchEvent(new Event("input", { bubbles: true }));
    Toast.show(REPLACED_TEXT, "success");

    state.start = next.caret;
    state.end = next.caret;
    close();
  }

  function onKeyDown(state, event) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }

    if (event.key !== "Tab") return;

    const list = focusables(state.els);
    if (!list.length) return;

    event.preventDefault();
    const index = list.indexOf(document.activeElement);
    list[nextFocusIndex(index, list.length, event.shiftKey ? -1 : 1)].focus();
  }

  function unbind(state) {
    const els = state.els;
    document.removeEventListener("keydown", state.onKey);
    els.mask.removeEventListener("click", state.onMaskClick);
    els.closeBtn.removeEventListener("click", close);
    els.cancel.removeEventListener("click", close);
    els.confirm.removeEventListener("click", state.onConfirm);
    els.retry.removeEventListener("click", state.onRetry);
  }

  function close() {
    if (!current) return;

    const state = current;
    current = null;
    unbind(state);

    state.els.mask.classList.remove("is-visible");
    state.els.mask.hidden = true;
    restoreFocus(state);
  }

  /**
   * 打开润色弹窗。返回本次请求的 Promise，便于调用方（与测试）等待结果。
   * options: { textarea, start, end, text }
   */
  function open(options) {
    const els = grab();
    if (!els.mask || !els.modal) return Promise.resolve(null);
    if (current) close();

    const state = {
      textarea: options.textarea,
      start: options.start,
      end: options.end,
      source: options.text,
      result: "",
      status: "loading",
      applied: false,
      els: els,
    };
    current = state;

    els.source.value = state.source;
    els.result.value = "";
    els.badge.textContent = "";
    els.badge.hidden = true;
    els.hint.textContent = "";
    els.error.textContent = "";
    setLoading(els);
    els.mask.hidden = false;
    els.mask.classList.add("is-visible");

    state.onKey = function (event) {
      onKeyDown(state, event);
    };
    state.onMaskClick = function (event) {
      if (event.target === els.mask) close();
    };
    state.onConfirm = function () {
      confirmReplace(state);
    };
    state.onRetry = function () {
      request(state);
    };

    document.addEventListener("keydown", state.onKey);
    els.mask.addEventListener("click", state.onMaskClick);
    els.closeBtn.addEventListener("click", close);
    els.cancel.addEventListener("click", close);
    els.confirm.addEventListener("click", state.onConfirm);
    els.retry.addEventListener("click", state.onRetry);

    focusFirst(els);

    return request(state);
  }

  window.AiPolish = {
    open: open,
    close: close,
    replaceSelection: replaceSelection,
    hasSelection: hasSelection,
    menuPosition: menuPosition,
    isMenuKey: isMenuKey,
    nextFocusIndex: nextFocusIndex,
    canConfirm: canConfirm,
    badgeText: badgeText,
  };
})();
