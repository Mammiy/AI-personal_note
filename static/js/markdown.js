/**
 * Markdown 渲染与消毒：预览区与详情页共用的唯一渲染入口。
 * 顺序固定为 marked 渲染 → DOMPurify 消毒，任何页面都不得绕过消毒直接插入 HTML。
 */
(function () {
  // alt/title 不在 DOMPurify 默认白名单里，正文图片与链接提示需要保留
  var SANITIZE_CONFIG = { ADD_ATTR: ["alt", "title"] };

  function renderMarkdown(md) {
    marked.setOptions({ gfm: true, breaks: true });
    var html = marked.parse(md || "");
    return DOMPurify.sanitize(html, SANITIZE_CONFIG);
  }

  window.renderMarkdown = renderMarkdown;
})();
