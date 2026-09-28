/**
 * 注册页：前端即时校验 + 提交。
 * 后端返回的错误一律展示后端 message，前端不拼接业务文案。
 */
(function () {
  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  const FIELDS = {
    email: { input: "email", wrap: "field-email", error: "email-error" },
    username: { input: "username", wrap: "field-username", error: "username-error" },
    password: { input: "password", wrap: "field-password", error: "password-error" },
    confirm: { input: "confirm", wrap: "field-confirm", error: "confirm-error" },
  };

  function el(id) {
    return document.getElementById(id);
  }

  function clearErrors() {
    el("form-error").textContent = "";
    Object.keys(FIELDS).forEach(function (key) {
      el(FIELDS[key].error).textContent = "";
      el(FIELDS[key].wrap).classList.remove("field--error");
    });
  }

  function showError(key, message) {
    if (!key || !FIELDS[key]) {
      el("form-error").textContent = message;
      return;
    }
    el(FIELDS[key].error).textContent = message;
    el(FIELDS[key].wrap).classList.add("field--error");
    el(FIELDS[key].input).focus();
  }

  /** 前端即时校验：只用需求文档给定的必填校验文案 */
  function localCheck(values) {
    if (!values.email) return { key: "email", message: "请填写邮箱" };
    if (!EMAIL_RE.test(values.email)) return { key: "email", message: "邮箱格式不正确" };
    if (!values.username) return { key: "username", message: "请填写用户名" };
    if (values.username.length < 2 || values.username.length > 20) {
      return { key: "username", message: "用户名需为 2 至 20 个字符" };
    }
    if (!values.password) return { key: "password", message: "请填写密码" };
    if (values.password.length < 6) return { key: "password", message: "密码至少需要 6 位" };
    if (values.password !== values.confirm) {
      return { key: "confirm", message: "两次输入的密码不一致" };
    }
    return null;
  }

  /** 后端 message 落到对应字段，文案本身原样展示 */
  function fieldKeyOf(message) {
    if (message.indexOf("邮箱") >= 0) return "email";
    if (message.indexOf("用户名") >= 0) return "username";
    if (message.indexOf("不一致") >= 0) return "confirm";
    if (message.indexOf("密码") >= 0) return "password";
    return null;
  }

  document.addEventListener("DOMContentLoaded", function () {
    const form = el("register-form");
    if (!form) return;

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      clearErrors();

      const values = {
        email: el("email").value.trim(),
        username: el("username").value.trim(),
        password: el("password").value,
        confirm: el("confirm").value,
      };

      const problem = localCheck(values);
      if (problem) {
        showError(problem.key, problem.message);
        return;
      }

      const button = el("submit-btn");
      button.disabled = true;
      button.textContent = "注册中…";

      Api.post("/api/auth/register", values)
        .then(function () {
          window.location.href = "/workspace";
        })
        .catch(function (error) {
          showError(fieldKeyOf(error.message || ""), error.message || "服务器繁忙，请稍后重试");
        })
        .finally(function () {
          button.disabled = false;
          button.textContent = "注册";
        });
    });
  });
})();
