import axios, { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import api, { refreshAccessToken } from './api'
import { useAuthStore } from '@/stores/authStore'

describe('memory-only credentials and refresh concurrency', () => {
  const originalAdapter = api.defaults.adapter
  beforeEach(() => { localStorage.clear(); useAuthStore.getState().clearAuth() })
  afterEach(() => { vi.restoreAllMocks(); api.defaults.adapter = originalAdapter })

  it('shares a single cookie refresh between concurrent requests', async () => {
    const post = vi.spyOn(axios, 'post').mockResolvedValue({ data: { access_token: 'access' } })
    const first = refreshAccessToken()
    const second = refreshAccessToken()
    expect(first).toBe(second)
    await expect(first).resolves.toBe('access')
    expect(post).toHaveBeenCalledOnce()
    expect(post.mock.calls[0]).toEqual(['/api/v1/auth/refresh', {}, { withCredentials: true }])
    expect(useAuthStore.getState().accessToken).toBe('access')
    expect(localStorage.length).toBe(0)
  })

  it('does not restore an old session after logout during a refresh', async () => {
    let finish: (value: { data: { access_token: string } }) => void = () => undefined
    vi.spyOn(axios, 'post').mockReturnValue(new Promise((resolve) => { finish = resolve }))
    const pending = refreshAccessToken()
    useAuthStore.getState().clearAuth()
    finish({ data: { access_token: 'old-session' } })
    await expect(pending).rejects.toThrow('Session changed')
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it('does not replay an old channel request using a different account', async () => {
    const refresh = vi.spyOn(axios, 'post')
    api.defaults.adapter = async (config) => {
      useAuthStore.getState().clearAuth()
      throw new AxiosError('Session changed', undefined, config, undefined, {
        data: {}, status: 401, statusText: 'Unauthorized', headers: new AxiosHeaders(), config,
      })
    }
    await expect(api.put('/external-notifications/channels/7', { name: 'Old user draft' })).rejects.toThrow('Session changed')
    expect(refresh).not.toHaveBeenCalled()
  })
})
