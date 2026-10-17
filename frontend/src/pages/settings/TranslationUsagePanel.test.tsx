import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import TranslationUsagePanel from './TranslationUsagePanel'

const mocked = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }))
vi.mock('@/services/api', () => ({ default: mocked }))
beforeEach(() => {
  vi.clearAllMocks()
  mocked.get.mockImplementation(async (url: string) => ({ data: url === '/ai/settings' ? {
    translation_max_input_tokens: 12000, translation_max_output_tokens: 4096,
    translation_article_token_limit: 100000, translation_monthly_token_limit: 50000,
    translation_max_requests: 32, translate_prompt: 'Do not overwrite this prompt',
  } : { reported_tokens: 0, budget_tokens: 4200, requests: 1, unreported_requests: 1,
    total: 1, page: 1, page_size: 10, items: [{ id: 1, article_id: 7, model: 'Fake', status: 'unknown',
      input_tokens: null, output_tokens: null, total_tokens: null, budget_tokens: 4200,
      created_at: '2026-10-17T00:00:00', error: 'Unknown result' }],
  } }))
  mocked.put.mockResolvedValue({ data: {} })
})
afterEach(cleanup)
function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TranslationUsagePanel />
  </QueryClientProvider>)
}
it('distinguishes unknown usage from zero and exposes reserved tokens', async () => {
  show()
  expect(await screen.findByText('未返回')).toBeTruthy()
  expect(screen.getByText('结果待核对')).toBeTruthy()
  expect(screen.getByText('— / —')).toBeTruthy()
})
it('saves only limits and clears an optional monthly limit explicitly', async () => {
  show()
  const limit = await screen.findByLabelText('每月累计 token 预算（留空不设限）')
  fireEvent.change(limit, { target: { value: '' } })
  fireEvent.click(screen.getByRole('button', { name: '保存翻译限额' }))
  await waitFor(() => expect(mocked.put).toHaveBeenCalledWith('/ai/settings', {
    translation_max_input_tokens: 12000, translation_max_output_tokens: 4096,
    translation_article_token_limit: 100000, translation_monthly_token_limit: null,
    translation_max_requests: 32,
  }))
})
