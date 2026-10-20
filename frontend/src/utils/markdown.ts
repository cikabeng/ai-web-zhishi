import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

// html: false —— 模型/模板输出一律按纯 Markdown 处理，不允许内嵌 HTML；
// 渲染后再过一遍 DOMPurify，双重保险。
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

export function renderMarkdown(text: string): string {
  return DOMPurify.sanitize(md.render(text))
}
