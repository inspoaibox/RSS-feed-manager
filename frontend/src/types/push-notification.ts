/**
 * Push notification types for frontend
 */

export type SubscriptionType = 'feed' | 'category' | 'keyword'
export type PushStatus = 'sent' | 'read' | 'clicked' | 'failed'

export interface QuietHours {
  start: string // HH:MM format
  end: string   // HH:MM format
}

export interface NotificationSubscription {
  id: number
  user_id: number
  name: string
  subscription_type: SubscriptionType
  target_id?: number
  keyword?: string
  is_enabled: boolean
  browser_notification: boolean
  desktop_notification: boolean
  quiet_hours?: string
  created_at: string
  updated_at: string
  target_name?: string
}

export interface SubscriptionCreate {
  name: string
  subscription_type: SubscriptionType
  target_id?: number
  keyword?: string
  browser_notification: boolean
  desktop_notification: boolean
  quiet_hours?: QuietHours
}

export interface SubscriptionUpdate {
  name?: string
  is_enabled?: boolean
  browser_notification?: boolean
  desktop_notification?: boolean
  quiet_hours?: QuietHours
}

export interface SubscriptionListResponse {
  subscriptions: NotificationSubscription[]
  total: number
}

export interface NotificationPush {
  id: number
  user_id: number
  subscription_id: number
  article_id: number
  status: PushStatus
  pushed_at: string
  read_at?: string
  clicked_at?: string
  subscription_name: string
  article_title: string
  article_link?: string
}

export interface PushListResponse {
  pushes: NotificationPush[]
  total: number
  page: number
  size: number
}

export interface PushStats {
  total_pushes: number
  unread_pushes: number
  clicked_pushes: number
}

export interface WebPushSubscription {
  endpoint: string
  keys: {
    p256dh: string
    auth: string
  }
  user_agent?: string
}

export interface VAPIDPublicKeyResponse {
  public_key: string
}
