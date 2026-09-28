/**
 * 通用交互：Toast 提示、二次确认弹窗、复制。
 * 错误文案全部来自后端 message，这里只负责呈现。
 */
const Toast = (() => {
  const DURATION = 2500;
  let timer = null;
  let hideTimer = null;

  function el() {
    let node = document.querySelector(".toast");
    if (!node) {
      node = document.createElement("div");
      node.className = "toast";
      node.setAttribute("role", "status");
      node.setAttribute("aria-live", "polite");
      document.body.appendChild(node);
    }
    return node;
  }

  function show(message, type = "error") {
    const node = el();
    node.textContent = message;
    node.className = "toast toast--" + (type === "success" ? "success" : "error");
    node.hidden = false;
    requestAnimationFrame(() => node.classList.add("is-visible"));

    clearTimeout(timer);
    clearTimeout(hideTimer);
    timer = setTimeout(() => {
      node.classList.remove("is-visible");
      hideTimer = setTimeout(() => {
        node.hidden = true;
      }, 200);
    }, DURATION);
  }

  return { show };
})();

const UI = (() => {
  function openModal({ title, body, confirmText = "确定", danger = false }) {
    return new Promise((resolve) => {
      const mask = document.createElement("div");
      mask.className = "modal-mask";

      const modal = document.createElement("div");
      modal.className = "modal";
      modal.setAttribute("role", "dialog");
      modal.setAttribute("aria-modal", "true");

      const head = document.createElement("h2");
      head.className = "modal__title";
      head.textContent = title;

      const content = document.createElement("div");
      content.className = "modal__body";
      content.textContent = body;

      const actions = document.createElement("div");
      actions.className = "modal__actions";

      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "btn btn--outline";
      cancel.textContent = "取消";

      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.className = danger ? "btn btn--danger" : "btn btn--primary";
      confirm.textContent = confirmText;

      actions.appendChild(cancel);
      actions.appendChild(confirm);
      modal.appendChild(head);
      modal.appendChild(content);
      modal.appendChild(actions);
      mask.appendChild(modal);
      document.body.appendChild(mask);

      requestAnimationFrame(() => mask.classList.add("is-visible"));

      function close(result) {
        mask.classList.remove("is-visible");
        setTimeout(() => mask.remove(), 160);
        document.removeEventListener("keydown", onKey);
        resolve(result);
      }

      function onKey(event) {
        if (event.key === "Escape") close(false);
      }

      cancel.addEventListener("click", () => close(false));
      confirm.addEventListener("click", () => close(true));
      mask.addEventListener("click", (event) => {
        if (event.target === mask) close(false);
      });
      document.addEventListener("keydown", onKey);

      confirm.focus();
    });
  }

  /** 删除等危险操作的二次确认，返回 Promise<boolean> */
  function confirm(text) {
    return openModal({ title: "请确认", body: text, confirmText: "确定", danger: true });
  }

  /** 复制链接等文本，成功提示「已复制链接」 */
  async function copy(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const input = document.createElement("textarea");
        input.value = text;
        input.setAttribute("readonly", "readonly");
        input.style.position = "fixed";
        input.style.opacity = "0";
        document.body.appendChild(input);
        input.select();
        document.execCommand("copy");
        input.remove();
      }
      Toast.show("已复制链接", "success");
      return true;
    } catch (e) {
      Toast.show("复制失败，请手动复制");
      return false;
    }
  }

  return { confirm, copy };
})();
