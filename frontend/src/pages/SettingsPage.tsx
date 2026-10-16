import { Tab } from '@/pages/settings/shared'
import { useAuthStore } from '@/stores/authStore'
import { Bell, Shield } from 'lucide-react'
import { lazy,Suspense,useState } from 'react'
const FeedsTab = lazy(() => import('@/pages/settings/FeedsTab'))
const ProxyPoolTab = lazy(() => import('@/pages/settings/ProxyPoolTab'))
const CategoriesTab = lazy(() => import('@/pages/settings/CategoriesTab'))
const AITab = lazy(() => import('@/pages/settings/AITab'))
const RulesTab = lazy(() => import('@/pages/settings/RulesTab'))
const BackupTab = lazy(() => import('@/pages/settings/BackupTab'))
const AppearanceTab = lazy(() => import('@/pages/settings/AppearanceTab'))
const SystemTab = lazy(() => import('@/pages/settings/SystemTab'))
const NotificationsTab = lazy(() => import('@/pages/settings/NotificationsTab'))

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('feeds')
  const user = useAuthStore((state) => state.user)
  const isAdmin = user?.is_admin ?? false

  const tabs = [
    { id: 'feeds', label: '订阅源' },
    { id: 'categories', label: '分类' },
    { id: 'ai', label: 'AI 设置' },
    { id: 'rules', label: '自定义规则' },
    { id: 'proxies', label: '代理池' },
    { id: 'backup', label: '备份恢复' },
    { id: 'appearance', label: '外观' },
    { id: 'notifications', label: '通知' },
    ...(isAdmin ? [{ id: 'system', label: '系统设置', icon: Shield }] : []),
  ]

  // Render tab content - only render active tab to reduce initial load
  const renderTabContent = () => {
    switch (activeTab) {
      case 'feeds':
        return <FeedsTab />
      case 'categories':
        return <CategoriesTab />
      case 'ai':
        return <AITab />
      case 'rules':
        return <RulesTab />
      case 'proxies':
        return <ProxyPoolTab />
      case 'backup':
        return <BackupTab />
      case 'appearance':
        return <AppearanceTab />
      case 'system':
        return isAdmin ? <SystemTab /> : null
      case 'notifications':
        return <NotificationsTab />
      default:
        return null
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 dark:text-white">设置</h1>
      
      {/* Tabs */}
      <div className="flex border-b dark:border-gray-700 mb-6 flex-wrap">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as Tab)}
            className={`px-4 py-2 border-b-2 -mb-px flex items-center gap-1 ${
              activeTab === tab.id
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
            }`}
          >
            {tab.id === 'system' && <Shield className="w-4 h-4" />}
            {tab.id === 'notifications' && <Bell className="w-4 h-4" />}
            {tab.label}
          </button>
        ))}
      </div>

      <Suspense fallback={<p className="text-gray-500">加载设置中…</p>}>{renderTabContent()}</Suspense>
    </div>
  )
}
