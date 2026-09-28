/**
 * 编辑器纯函数：只做文本变换，不碰 DOM。
 * 页面脚本负责把 <textarea> 的 selectionStart/End 传进来，再把结果写回。
 * 统一返回 { value, start, end }：start/end 为变换后应保留的选区。
 */
(function () {
  /** 包裹类：加粗 **、斜体 *、行内代码 ` */
  function wrap(value, start, end, marker) {
    const selected = value.slice(start, end);
    return {
      value: value.slice(0, start) + marker + selected + marker + value.slice(end),
      start: start + marker.length,
      end: start + marker.length + selected.length,
    };
  }

  /** 行前缀类：# 、## 、> 、- 、1. ，作用于每个选中行的行首，已存在则移除 */
  function prefixLines(value, start, end, prefix) {
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    let lineEnd = value.indexOf("\n", end);
    if (lineEnd === -1) lineEnd = value.length;

    const block = value.slice(lineStart, lineEnd);
    const next = block
      .split("\n")
      .map((line) =>
        line.startsWith(prefix) ? line.slice(prefix.length) : prefix + line
      )
      .join("\n");

    return {
      value: value.slice(0, lineStart) + next + value.slice(lineEnd),
      start: lineStart,
      end: lineStart + next.length,
    };
  }

  /** 插入 [文字](url)，并把 url 占位选中，方便直接粘贴地址 */
  function insertLink(value, start, end) {
    const text = value.slice(start, end) || "文字";
    const urlStart = start + text.length + 3; // "[" + 文字 + "](" 的长度
    return {
      value: value.slice(0, start) + "[" + text + "](url)" + value.slice(end),
      start: urlStart,
      end: urlStart + 3,
    };
  }

  /** 插入 ![说明](url)，光标停在插入内容末尾 */
  function insertImage(value, start, end, url, alt) {
    const snippet = "![" + (alt || "") + "](" + url + ")";
    const caret = start + snippet.length;
    return {
      value: value.slice(0, start) + snippet + value.slice(end),
      start: caret,
      end: caret,
    };
  }

  window.Editor = { wrap, prefixLines, insertLink, insertImage };
})();
