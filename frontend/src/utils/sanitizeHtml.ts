import DOMPurify from 'dompurify'

export const sanitizeHtml = (html: string): string => DOMPurify.sanitize(html, {
  FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button'],
  FORBID_ATTR: ['style', 'srcdoc'],
  ALLOW_DATA_ATTR: false,
})
