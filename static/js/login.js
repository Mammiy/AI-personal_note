/**
 * 登录页：提交后由 api.js 统一处理后端 message，失败时已填内容保留。
 */
(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function clearErrors() {
    el("form-error").textContent = "";
    ["field-email", "field-password"].forEach(function (id) {
      el(id).classList.remove("field--error");
    });
    el("email-error").textContent = "";
    el("password-error").textContent = "";
  }

  function showError(key, message) {
    if (key === "password") {
      el("password-error").textContent = message;
      el("field-password").classList.add("field--error");
      el("password").focus();
      return;
    }
    if (key === "email") {
      el("email-error").textContent = message;
      el("field-email").classList.add("field--error");
      el("email").focus();
      return;
    }
    el("form-error").textContent = message;
  }

  document.addEventListener("DOMContentLoaded", function () {
    const form = el("login-form");
    if (!form) return;

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      clearErrors();

      const values = {
        email: el("email").value.trim(),
        password: el("password").value,
      };

      if (!values.email) {
        showError("email", "请填写邮箱");
        return;
      }
      if (!values.password) {
        showError("password", "请填写密码");
        return;
      }

      const button = el("submit-btn");
      button.disabled = true;
      button.textContent = "登录中…";

      Api.post("/api/auth/login", values)
        .then(function () {
          window.location.href = "/workspace";
        })
        .catch(function (error) {
          const message = error.message || "服务器繁忙，请稍后重试";
          showError(message.indexOf("密码") >= 0 ? "password" : null, message);
        })
        .finally(function () {
          button.disabled = false;
          button.textContent = "登录";
        });
    });
  });
})();
