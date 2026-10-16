import { expect, it } from 'vitest'
import { safeExternalUrl } from './safeExternalUrl'

it('blocks script and data URLs in article links', () => {
  for (const value of ['javascript:alert(1)', 'data:text/html,<script>evil</script>', 'file:///secret', '/relative']) {
    expect(safeExternalUrl(value)).toBeUndefined()
  }
  expect(safeExternalUrl('https://example.com/article')).toBe('https://example.com/article')
})
