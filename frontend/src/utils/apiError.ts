import axios from 'axios'

export const getApiErrorMessage = (error: unknown, fallback: string): string => {
  if (!axios.isAxiosError<{ detail?: unknown; message?: unknown }>(error)) return fallback
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item: unknown) => {
      if (item && typeof item === 'object' && 'msg' in item) return String(item.msg)
      return String(item)
    }).join(', ')
  }
  if (typeof detail === 'string' && detail) return detail
  const message = error.response?.data?.message
  return typeof message === 'string' && message ? message : fallback
}
