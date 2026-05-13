// Notification types
export interface Notification {
  id: number
  title: string
  content: string
  type: 'system' | 'update' | 'maintenance'
  is_active: boolean
  created_by: number | null
  creator_name: string | null
  expires_at: string | null
  created_at: string
}

export interface NotificationListResponse {
  notifications: Notification[]
  total: number
}

export interface UnreadCountResponse {
  count: number
}

export interface MarkReadResponse {
  success: boolean
  message: string
}

export interface NotificationCreate {
  title: string
  content: string
  type: 'system' | 'update' | 'maintenance'
  expires_at?: string | null
}

export interface NotificationUpdate {
  title?: string
  content?: string
  type?: 'system' | 'update' | 'maintenance'
  is_active?: boolean
  expires_at?: string | null
}
