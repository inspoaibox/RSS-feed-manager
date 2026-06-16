import { useState, useEffect } from 'react'
import { Check, AlertTriangle, Bell } from 'lucide-react'
import api from '@/services/api'

export default function BrowserPermissionStatus() {
  const [permission, setPermission] = useState<NotificationPermission>('default')
  const [isRequesting, setIsRequesting] = useState(false)

  useEffect(() => {
    if ('Notification' in window) {
      setPermission(Notification.permission)
    }
  }, [])

  const requestPermission = async () => {
    if (!('Notification' in window)) {
      alert('您的浏览器不支持桌面通知')
      return
    }

    setIsRequesting(true)
    try {
      const result = await Notification.requestPermission()
      setPermission(result)

      if (result === 'granted') {
        // Subscribe to Web Push
        await subscribeToWebPush()
      }
    } catch (error) {
      console.error('Failed to request notification permission:', error)
    } finally {
      setIsRequesting(false)
    }
  }

  const subscribeToWebPush = async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      console.error('浏览器不支持 Push API')
      return
    }

    try {
      // Register service worker
      const registration = await navigator.serviceWorker.register('/sw.js')
      await navigator.serviceWorker.ready

      // Get VAPID public key
      const response = await api.get('/push-notifications/web-push/public-key')
      const publicKey = response.data.public_key

      // Subscribe to push
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
      })

      // Send subscription to backend
      await api.post('/push-notifications/web-push/subscribe', {
        endpoint: subscription.endpoint,
        keys: {
          p256dh: arrayBufferToBase64(subscription.getKey('p256dh') as ArrayBuffer),
          auth: arrayBufferToBase64(subscription.getKey('auth') as ArrayBuffer),
        },
        user_agent: navigator.userAgent,
      })

      console.log('Web Push 订阅成功')
    } catch (error) {
      console.error('Web Push 订阅失败:', error)
    }
  }

  if (permission === 'granted') {
    return (
      <div className="p-4 border dark:border-gray-700 rounded-lg bg-green-50 dark:bg-green-900/20">
        <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
          <Check className="w-5 h-5" />
          <span className="font-medium">浏览器通知已启用</span>
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
          您将收到订阅内容的实时推送通知
        </p>
      </div>
    )
  }

  if (permission === 'denied') {
    return (
      <div className="p-4 border dark:border-gray-700 rounded-lg bg-red-50 dark:bg-red-900/20">
        <div className="flex items-center gap-2 text-red-600 dark:text-red-400 mb-2">
          <AlertTriangle className="w-5 h-5" />
          <span className="font-medium">浏览器通知已被阻止</span>
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          请在浏览器设置中允许通知权限：
        </p>
        <ol className="text-sm text-gray-600 dark:text-gray-400 mt-2 ml-4 list-decimal space-y-1">
          <li>点击地址栏左侧的锁图标</li>
          <li>找到"通知"权限设置</li>
          <li>选择"允许"</li>
          <li>刷新页面</li>
        </ol>
      </div>
    )
  }

  return (
    <div className="p-4 border dark:border-gray-700 rounded-lg">
      <div className="flex items-start gap-3">
        <Bell className="w-5 h-5 text-primary-600 dark:text-primary-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h4 className="font-medium dark:text-white mb-1">启用浏览器通知</h4>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
            启用后，即使关闭页面也能收到重要更新提醒
          </p>
          <button
            onClick={requestPermission}
            disabled={isRequesting}
            className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50 text-sm"
          >
            {isRequesting ? '请求中...' : '启用浏览器通知'}
          </button>
        </div>
      </div>
    </div>
  )
}

// Helper functions
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')

  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return window.btoa(binary)
}
