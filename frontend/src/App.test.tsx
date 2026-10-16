import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { queryClient } from '@/queryClient'
import { useAuthStore } from '@/stores/authStore'
import App from './App'

vi.mock('@/services/api', () => ({
  default: { get: vi.fn(async () => ({ data: { allow_registration: true, has_users: true, site_name: 'RSS' } })) },
  refreshAccessToken: vi.fn(async () => { throw new Error('No session') }),
}))

afterEach(() => { cleanup(); queryClient.clear() })

it('finishes bootstrap and displays login when no refresh cookie exists', async () => {
  useAuthStore.setState({ isInitialized: false, isAuthenticated: false, user: null, accessToken: null })
  localStorage.setItem('auth-storage', 'legacy credentials')
  await act(async () => {
    render(<QueryClientProvider client={queryClient}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>)
  })
  await waitFor(() => expect(screen.getByRole('button', { name: '登录' })).toBeTruthy())
  expect(localStorage.getItem('auth-storage')).toBeNull()
  expect(useAuthStore.getState().isInitialized).toBe(true)
})
