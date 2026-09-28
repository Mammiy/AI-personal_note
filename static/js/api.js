/**
 * 前端唯一请求出口。
 * 页面脚本禁止直接 fetch，一律走这里：统一解析 {code, message, data}，
 * code != "OK" 时只展示后端 message，遇到未授权统一跳登录页。
 */
const Api = (() => {
  const UNAUTHORIZED_REDIRECT_DELAY = 800;

  async function request(path, { method = "GET", body = null, form = null } = {}) {
    const opts = { method, credentials: "same-origin", headers: {} };
    if (form) {
      opts.body = form;
    } else if (body !== null) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }

    const res = await fetch(path, opts);

    let data;
    try {
      data = await res.json();
    } catch (e) {
      Toast.show("服务器繁忙，请稍后重试");
      throw e;
    }

    if (data.code === "OK") return data.data;

    const msg = data.message || "服务器繁忙，请稍后重试";
    if (data.code === "UNAUTHORIZED") {
      Toast.show(msg);
      setTimeout(() => {
        window.location.href = "/login";
      }, UNAUTHORIZED_REDIRECT_DELAY);
      throw new Error(msg);
    }

    Toast.show(msg);
    const err = new Error(msg);
    err.code = data.code;
    throw err;
  }

  return {
    get: (path) => request(path),
    post: (path, body) => request(path, { method: "POST", body }),
    put: (path, body) => request(path, { method: "PUT", body }),
    del: (path) => request(path, { method: "DELETE" }),
    upload: (path, form) => request(path, { method: "POST", form }),
  };
})();
