import { describe, expect, it } from 'vitest'
import { sanitizeHtml } from './sanitizeHtml'

describe('untrusted article and notification HTML', () => {
  it('removes executable attributes, scripts, CSS and embedded frames', () => {
    const node = document.createElement('div')
    node.innerHTML = sanitizeHtml('<script>alert(1)</script><img src="x" onerror="alert(1)">' +
      '<iframe srcdoc="evil"></iframe><a href="javascript:alert(1)">link</a>' +
      '<p style="position:fixed" onclick="evil()">Safe text</p>')
    expect(node.querySelector('script,iframe')).toBeNull()
    expect(node.querySelector('[onerror],[onclick],[style]')).toBeNull()
    expect(node.querySelector('a')?.getAttribute('href')).toBeNull()
    expect(node.textContent).toContain('Safe text')
  })

  it('retains readable formatting and normal HTTPS links', () => {
    const result = sanitizeHtml('<h2>Title</h2><p><strong>Text</strong> <a href="https://example.com">Source</a></p>')
    expect(result).toContain('<strong>Text</strong>')
    expect(result).toContain('href="https://example.com"')
  })
})
