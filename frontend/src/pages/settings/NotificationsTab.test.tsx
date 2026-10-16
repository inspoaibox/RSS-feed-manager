import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/authStore'
import SettingsPage from '@/pages/SettingsPage'
import NotificationsTab from './NotificationsTab'

const mocked = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }))
vi.mock('@/services/api', () => ({ default: mocked }))
const workChannel = { id: 7, name: 'Work', provider: 'feishu', is_enabled: true,
  has_webhook: true, has_signing_secret: false, has_bot_token: false, chat_id: null, message_thread_id: null }

beforeEach(() => {
  vi.clearAllMocks()
  mocked.get.mockImplementation(async (url: string) => ({ data:
    url.endsWith('/channels') ? [workChannel] :
    url === '/feeds' ? [{ id: 2, title: 'RSS feed' }] :
    url === '/categories' ? [{ id: 3, name: 'Technology' }] :
    url.endsWith('/deliveries') ? { items: [], total: 0, page: 1, page_size: 20 } : [],
  }))
  mocked.post.mockResolvedValue({ data: { success: true, message: '测试消息已发送' } })
  mocked.put.mockResolvedValue({ data: workChannel })
})
afterEach(cleanup)

function show(element = <NotificationsTab />) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{element}</QueryClientProvider>)
}

it('makes the notification entry available to ordinary users', async () => {
  useAuthStore.setState({ user: { id: 1, username: 'user', email: 'user@example.com', is_admin: false, created_at: '' } })
  show(<SettingsPage />)
  expect(screen.queryByRole('button', { name: '系统设置' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '通知' }))
  expect(await screen.findByRole('tab', { name: '通知频道' })).toBeTruthy()
})

it('saves a Feishu channel using the entered credentials', async () => {
  show()
  await screen.findByText('Work')
  fireEvent.click(screen.getByRole('button', { name: '添加频道' }))
  fireEvent.change(screen.getByLabelText('频道名称'), { target: { value: 'My Feishu' } })
  fireEvent.change(screen.getByLabelText('Webhook 地址'), { target: { value: 'https://open.feishu.cn/open-apis/bot/v2/hook/token' } })
  fireEvent.click(screen.getByRole('button', { name: '保存频道' }))
  await waitFor(() => expect(mocked.post).toHaveBeenCalledWith('/external-notifications/channels', {
    name: 'My Feishu', provider: 'feishu', is_enabled: true,
    config: { webhook_url: 'https://open.feishu.cn/open-apis/bot/v2/hook/token', signing_secret: '' },
  }))
})

it('lets users connect a category to selected channels', async () => {
  show()
  await screen.findByText('Work')
  fireEvent.click(screen.getByRole('tab', { name: '推送规则' }))
  fireEvent.click(screen.getByRole('button', { name: '添加规则' }))
  fireEvent.change(screen.getByLabelText('规则名称'), { target: { value: 'Tech updates' } })
  fireEvent.change(screen.getByLabelText('推送来源'), { target: { value: '3' } })
  fireEvent.click(screen.getByLabelText('Work'))
  fireEvent.click(screen.getByRole('button', { name: '保存规则' }))
  await waitFor(() => expect(mocked.post).toHaveBeenCalledWith('/external-notifications/rules', {
    name: 'Tech updates', source_type: 'category', source_id: 3, channel_ids: [7], is_enabled: true,
  }))
})

it('shows test results and delivery history', async () => {
  show()
  await screen.findByText('Work')
  fireEvent.click(screen.getByRole('button', { name: '测试发送' }))
  expect(await screen.findByText('测试消息已发送')).toBeTruthy()
  expect(mocked.post).toHaveBeenCalledWith('/external-notifications/channels/7/test')
  fireEvent.click(screen.getByRole('tab', { name: '发送记录' }))
  expect(await screen.findByText('暂无发送记录。频道测试和新文章推送都会在这里显示。')).toBeTruthy()
})

it.each([
  { provider: 'wecom', fields: [['企业微信 Webhook 地址', 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=secret']],
    config: { webhook_url: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=secret' } },
  { provider: 'email', fields: [['SMTP 主机', 'smtp.qq.com'], ['SMTP 用户名', 'notify@qq.com'],
    ['SMTP 密码 / 授权码', 'smtp-secret'], ['发件邮箱', 'notify@qq.com'], ['收件邮箱', 'one@example.com;two@example.com']],
    config: { smtp_host: 'smtp.qq.com', smtp_port: 465, smtp_security: 'ssl', smtp_username: 'notify@qq.com',
      smtp_password: 'smtp-secret', smtp_from: 'notify@qq.com', smtp_to: ['one@example.com', 'two@example.com'] } },
  { provider: 'bark', fields: [['Device Key', 'bark-secret'], ['Bark 服务器（可选）', 'https://bark.example.com']],
    config: { server_url: 'https://bark.example.com', device_key: 'bark-secret', bark_group: 'RSS' } },
  { provider: 'pushplus', fields: [['PushPlus Token', 'pushplus-secret']],
    config: { pushplus_token: 'pushplus-secret', pushplus_channel: 'wechat', pushplus_topic: '', pushplus_option: '' } },
  { provider: 'serverchan', fields: [['SendKey', 'SCTsecret']], config: { serverchan_send_key: 'SCTsecret' } },
  { provider: 'webhook', fields: [['Webhook 地址', 'https://notify.example.com'], ['请求方法', 'PUT'],
    ['请求头 JSON（可选）', '{"Authorization":"Bearer secret"}'], ['请求体 JSON 模板（可选）', '{"text":"{{message}}"}']],
    config: { webhook_url: 'https://notify.example.com', webhook_method: 'PUT',
      webhook_headers: { Authorization: 'Bearer secret' }, webhook_body: { text: '{{message}}' } } },
])('saves $provider with only its own configuration fields', async ({ provider, fields, config }) => {
  show()
  await screen.findByText('Work')
  fireEvent.click(screen.getByRole('button', { name: '添加频道' }))
  fireEvent.change(screen.getByLabelText('频道名称'), { target: { value: 'My channel' } })
  fireEvent.change(screen.getByLabelText('通知应用'), { target: { value: provider } })
  for (const [label, value] of fields) fireEvent.change(screen.getByLabelText(label), { target: { value } })
  fireEvent.click(screen.getByRole('button', { name: '保存频道' }))
  await waitFor(() => expect(mocked.post).toHaveBeenCalledWith('/external-notifications/channels', {
    name: 'My channel', provider, is_enabled: true, config,
  }))
})

it('keeps stored webhook headers and templates when an edit leaves them blank', async () => {
  mocked.get.mockImplementation(async (url: string) => ({ data: url.endsWith('/channels') ? [{
    ...workChannel, provider: 'webhook', webhook_method: 'PUT', has_webhook_headers: true, has_webhook_body: true,
  }] : [] }))
  show()
  await screen.findByText('Work')
  fireEvent.click(screen.getByRole('button', { name: '编辑' }))
  expect((screen.getByLabelText('Webhook 地址') as HTMLInputElement).value).toBe('')
  expect((screen.getByLabelText('请求头 JSON（可选）') as HTMLTextAreaElement).value).toBe('')
  fireEvent.click(screen.getByRole('button', { name: '保存频道' }))
  await waitFor(() => expect(mocked.put).toHaveBeenCalledWith('/external-notifications/channels/7', {
    name: 'Work', provider: 'webhook', is_enabled: true, config: { webhook_url: '', webhook_method: 'PUT' },
  }))
})

it('lets users clear stored webhook authentication and restore the default body', async () => {
  mocked.get.mockImplementation(async (url: string) => ({ data: url.endsWith('/channels') ? [{
    ...workChannel, provider: 'webhook', has_webhook_headers: true, has_webhook_body: true,
  }] : [] }))
  show()
  await screen.findByText('Work')
  fireEvent.click(screen.getByRole('button', { name: '编辑' }))
  fireEvent.click(screen.getByLabelText('清除已保存的请求头'))
  fireEvent.click(screen.getByLabelText('恢复默认请求体'))
  fireEvent.click(screen.getByRole('button', { name: '保存频道' }))
  await waitFor(() => expect(mocked.put).toHaveBeenCalledWith('/external-notifications/channels/7', {
    name: 'Work', provider: 'webhook', is_enabled: true,
    config: { webhook_url: '', webhook_method: 'POST', webhook_headers: null, webhook_body: null },
  }))
})

it('rejects invalid JSON before saving a webhook channel', async () => {
  show()
  await screen.findByText('Work')
  fireEvent.click(screen.getByRole('button', { name: '添加频道' }))
  fireEvent.change(screen.getByLabelText('通知应用'), { target: { value: 'webhook' } })
  fireEvent.change(screen.getByLabelText('频道名称'), { target: { value: 'Hook' } })
  fireEvent.change(screen.getByLabelText('Webhook 地址'), { target: { value: 'https://notify.example.com' } })
  fireEvent.change(screen.getByLabelText('请求头 JSON（可选）'), { target: { value: '[]' } })
  fireEvent.click(screen.getByRole('button', { name: '保存频道' }))
  await screen.findByText('请求头必须是值为字符串的 JSON 对象')
  expect(mocked.post).not.toHaveBeenCalled()
})
