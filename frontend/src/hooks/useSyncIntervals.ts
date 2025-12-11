import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

export interface SyncIntervalOption {
  value: number
  label: string
}

interface PublicSettings {
  site_name: string
  sync_intervals: SyncIntervalOption[]
  default_sync_interval: number
}

export function useSyncIntervals() {
  const { data } = useQuery({
    queryKey: ['public-settings'],
    queryFn: async () => {
      const response = await api.get<PublicSettings>('/system/public-settings')
      return response.data
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  return {
    syncIntervals: data?.sync_intervals ?? [],
    defaultSyncInterval: data?.default_sync_interval ?? 3600,
  }
}
