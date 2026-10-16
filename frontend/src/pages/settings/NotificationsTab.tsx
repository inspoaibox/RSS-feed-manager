import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Edit2, Loader2, Plus, RefreshCw, Send, Trash2, X } from 'lucide-react'
import api from '@/services/api'
import type { Category, Feed } from '@/types'
import { getApiErrorMessage } from '@/utils/apiError'
import NotificationChannelFields from './NotificationChannelFields'
import { ChannelConfigError, channelConfig, channelFormFor, emptyChannel, providerNames, type Channel, type Provider } from './notificationChannels'

type SourceType = 'feed' | 'category'
type Section = 'channels' | 'rules' | 'history'
interface Rule {
  id: number; name: string; source_type: SourceType; source_id: number
  source_name: string | null; channel_ids: number[]; is_enabled: boolean
}
interface Delivery {
  id: number; channel_name: string; provider: Provider; article_title: string
  is_test: boolean; status: string; attempts: number; error: string | null
  created_at: string; sent_at: string | null
}
interface DeliveryList { items: Delivery[]; total: number; page: number; page_size: number }

const endpoint = '/external-notifications'
const statusNames: Record<string, string> = {
  pending: '待发送', queued: '已排队', sending: '发送中', sent: '已发送', failed: '发送失败', skipped: '已跳过',
}
const emptyRule = {
  name: '', source_type: 'category' as SourceType, source_id: '', channel_ids: [] as number[],
  is_enabled: true,
}
const buttonClass = 'inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50'
const primaryClass = 'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50'
const panelClass = 'rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5'
const inputClass = 'block w-full mt-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-white'

function formatTime(value: string) {
  const utcValue = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`
  return new Date(utcValue).toLocaleString('zh-CN')
}

export default function NotificationsTab() {
  const queryClient = useQueryClient()
  const [section, setSection] = useState<Section>('channels')
  const [notice, setNotice] = useState<{ success: boolean; text: string } | null>(null)
  const [channelForm, setChannelForm] = useState({ ...emptyChannel })
  const [channelEditor, setChannelEditor] = useState<number | 'new' | null>(null)
  const [ruleForm, setRuleForm] = useState({ ...emptyRule })
  const [ruleEditor, setRuleEditor] = useState<number | 'new' | null>(null)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')

  const channelsQuery = useQuery({
    queryKey: ['notification-channels'],
    queryFn: async () => (await api.get<Channel[]>(`${endpoint}/channels`)).data,
  })
  const channels = channelsQuery.data || []
  const rulesQuery = useQuery({
    queryKey: ['notification-rules'],
    queryFn: async () => (await api.get<Rule[]>(`${endpoint}/rules`)).data,
  })
  const rules = rulesQuery.data || []
  const { data: feeds = [] } = useQuery({
    queryKey: ['feeds'], queryFn: async () => (await api.get<Feed[]>('/feeds')).data,
  })
  const { data: categories = [] } = useQuery({
    queryKey: ['categories'], queryFn: async () => (await api.get<Category[]>('/categories')).data,
  })
  const historyQuery = useQuery({
    queryKey: ['notification-deliveries', page, status],
    queryFn: async () => (await api.get<DeliveryList>(`${endpoint}/deliveries`, {
      params: { page, page_size: 20, ...(status ? { status } : {}) },
    })).data,
    enabled: section === 'history', refetchInterval: section === 'history' ? 10000 : false,
  })
  const invalidate = () => {
    for (const key of ['notification-channels', 'notification-rules', 'notification-deliveries']) {
      queryClient.invalidateQueries({ queryKey: [key] })
    }
  }
  const showError = (error: unknown) => setNotice({ success: false, text: error instanceof ChannelConfigError ? error.message : getApiErrorMessage(error, '操作失败，请重试') })

  const saveChannel = useMutation({
    mutationFn: async () => {
      const config = channelConfig(channelForm, channelEditor === 'new')
      const data = { name: channelForm.name, provider: channelForm.provider, is_enabled: channelForm.is_enabled, config }
      if (channelEditor === 'new') await api.post(`${endpoint}/channels`, data)
      else await api.put(`${endpoint}/channels/${channelEditor}`, data)
    },
    onSuccess: () => {
      invalidate(); setChannelEditor(null); setChannelForm({ ...emptyChannel })
      setNotice({ success: true, text: '通知频道已保存，可以发送测试消息' })
    }, onError: showError,
  })
  const deleteChannel = useMutation({
    mutationFn: (id: number) => api.delete(`${endpoint}/channels/${id}`),
    onSuccess: () => { invalidate(); setNotice({ success: true, text: '频道已删除，历史记录保留' }) },
    onError: showError,
  })
  const testChannel = useMutation({
    mutationFn: async (id: number) => (await api.post<{ success: boolean; message: string }>(`${endpoint}/channels/${id}/test`)).data,
    onSuccess: (data) => { invalidate(); setNotice({ success: data.success, text: data.message }) },
    onError: showError,
  })
  const toggleChannel = useMutation({
    mutationFn: (channel: Channel) => api.put(`${endpoint}/channels/${channel.id}`, { is_enabled: !channel.is_enabled }),
    onSuccess: invalidate, onError: showError,
  })
  const saveRule = useMutation({
    mutationFn: async () => {
      const data = { ...ruleForm, source_id: Number(ruleForm.source_id) }
      if (ruleEditor === 'new') await api.post(`${endpoint}/rules`, data)
      else await api.put(`${endpoint}/rules/${ruleEditor}`, data)
    },
    onSuccess: () => {
      invalidate(); setRuleEditor(null); setRuleForm({ ...emptyRule })
      setNotice({ success: true, text: '推送规则已保存，后续新文章将自动推送' })
    }, onError: showError,
  })
  const toggleRule = useMutation({
    mutationFn: (rule: Rule) => api.put(`${endpoint}/rules/${rule.id}`, { ...rule, is_enabled: !rule.is_enabled }),
    onSuccess: invalidate, onError: showError,
  })
  const deleteRule = useMutation({
    mutationFn: (id: number) => api.delete(`${endpoint}/rules/${id}`),
    onSuccess: invalidate, onError: showError,
  })
  const retry = useMutation({
    mutationFn: (id: number) => api.post(`${endpoint}/deliveries/${id}/retry`),
    onSuccess: () => { invalidate(); setNotice({ success: true, text: '通知已加入重试队列' }) },
    onError: showError,
  })

  const openChannel = (channel?: Channel) => {
    setNotice(null)
    setChannelEditor(channel?.id || 'new')
    setChannelForm(channelFormFor(channel))
  }
  const openRule = (rule?: Rule) => {
    setNotice(null); setRuleEditor(rule?.id || 'new')
    setRuleForm(rule ? { name: rule.name, source_type: rule.source_type, source_id: String(rule.source_id),
      channel_ids: [...rule.channel_ids], is_enabled: rule.is_enabled } : { ...emptyRule, channel_ids: [] })
  }
  const sourceOptions = ruleForm.source_type === 'feed' ? feeds.map(feed => ({ id: feed.id, name: feed.title })) : categories
  const editedChannel = channels.find(channel => channel.id === channelEditor)
  const queryError = channelsQuery.error || rulesQuery.error || (section === 'history' ? historyQuery.error : null)

  return (
    <div className="space-y-5 text-gray-900 dark:text-gray-100">
      <div className={`${panelClass} flex items-start gap-3`}>
        <Bell className="h-5 w-5 text-primary-600 mt-0.5 shrink-0" />
        <div>
          <h2 className="font-semibold">把订阅更新发送到你的应用</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">支持飞书、Telegram、企业微信、邮件、Bark、PushPlus、Server酱和通用 Webhook。添加频道后选择分类或 RSS，所有配置仅属于当前账户。</p>
        </div>
      </div>
      {(notice || queryError) && <div role="status" className={`rounded-lg p-3 text-sm ${notice?.success ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'}`}>
        {notice?.text || getApiErrorMessage(queryError, '通知数据加载失败，请稍后重试')}
      </div>}
      <div role="tablist" aria-label="通知管理" className="flex gap-2 flex-wrap">
        {([['channels', '通知频道'], ['rules', '推送规则'], ['history', '发送记录']] as const).map(([id, label]) => (
          <button key={id} role="tab" aria-selected={section === id} onClick={() => { setSection(id); setNotice(null) }}
            className={section === id ? primaryClass : buttonClass}>{label}</button>
        ))}
      </div>

      {section === 'channels' && <div className="space-y-4">
        <div className="flex items-center justify-between"><h3 className="font-medium">我的频道（{channels.length}）</h3>
          <button className={primaryClass} onClick={() => openChannel()}><Plus size={16} />添加频道</button></div>
        {channelEditor !== null && <form className={`${panelClass} space-y-4`} onSubmit={event => { event.preventDefault(); saveChannel.mutate() }}>
          <div className="flex justify-between"><h3 className="font-semibold">{channelEditor === 'new' ? '添加通知频道' : '编辑通知频道'}</h3>
            <button type="button" aria-label="关闭频道编辑" onClick={() => setChannelEditor(null)}><X size={18} /></button></div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm">频道名称<input required maxLength={100} className={inputClass} value={channelForm.name} onChange={event => setChannelForm({ ...channelForm, name: event.target.value })} placeholder="例如：技术资讯群" /></label>
            <label className="text-sm">通知应用<select className={inputClass} value={channelForm.provider} disabled={channelEditor !== 'new'} onChange={event => setChannelForm({ ...emptyChannel, name: channelForm.name, is_enabled: channelForm.is_enabled, provider: event.target.value as Provider })}>
              {Object.entries(providerNames).map(([provider, name]) => <option key={provider} value={provider}>{name}</option>)}
            </select></label>
          </div>
          <NotificationChannelFields form={channelForm} setForm={setChannelForm} channel={editedChannel} isNew={channelEditor === 'new'} />
          <label className="flex gap-2 text-sm"><input type="checkbox" checked={channelForm.is_enabled} onChange={event => setChannelForm({ ...channelForm, is_enabled: event.target.checked })} />启用频道</label>
          <div className="flex gap-2"><button className={primaryClass} disabled={saveChannel.isPending}>{saveChannel.isPending && <Loader2 size={16} className="animate-spin" />}保存频道</button>
            <button type="button" className={buttonClass} onClick={() => setChannelEditor(null)}>取消</button></div>
        </form>}
        {channelsQuery.isLoading ? <p className="text-sm text-gray-500">加载频道中…</p> : channels.length === 0 ? <div className={`${panelClass} text-sm text-gray-500`}>还没有通知频道。先添加频道并测试，再创建推送规则。</div> : channels.map(channel => <div key={channel.id} className={`${panelClass} flex flex-wrap items-center justify-between gap-4`}>
          <div><h4 className="font-medium">{channel.name}</h4><p className="text-sm text-gray-500 mt-1">{providerNames[channel.provider]} · {channel.is_enabled ? '已启用' : '已停用'}{channel.chat_id ? ` · ${channel.chat_id}` : ''}</p></div>
          <div className="flex gap-2 flex-wrap">
            <button className={buttonClass} disabled={testChannel.isPending} onClick={() => testChannel.mutate(channel.id)}>{testChannel.isPending && testChannel.variables === channel.id ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}测试发送</button>
            <button className={buttonClass} onClick={() => openChannel(channel)}><Edit2 size={15} />编辑</button>
            <button className={buttonClass} disabled={toggleChannel.isPending} onClick={() => toggleChannel.mutate(channel)}>{channel.is_enabled ? '停用' : '启用'}</button>
            <button className={`${buttonClass} text-red-600`} disabled={deleteChannel.isPending} onClick={() => { if (confirm(`删除“${channel.name}”？规则将移除该频道，发送历史保留。`)) deleteChannel.mutate(channel.id) }}><Trash2 size={15} />删除</button>
          </div>
        </div>)}
      </div>}

      {section === 'rules' && <div className="space-y-4">
        <div className="flex items-center justify-between"><h3 className="font-medium">推送规则（{rules.length}）</h3>
          <button className={primaryClass} disabled={!channels.length} onClick={() => openRule()}><Plus size={16} />添加规则</button></div>
        <p className="text-sm text-gray-500">仅推送规则创建后的新文章。同一文章命中多条规则时，每个频道只发送一次；停用的频道不发送更新。</p>
        {!channels.length && <p className="text-sm text-primary-600">请先在“通知频道”中添加一个频道。</p>}
        {ruleEditor !== null && <form className={`${panelClass} space-y-4`} onSubmit={event => { event.preventDefault(); saveRule.mutate() }}>
          <div className="flex justify-between"><h3 className="font-semibold">{ruleEditor === 'new' ? '添加推送规则' : '编辑推送规则'}</h3><button type="button" aria-label="关闭规则编辑" onClick={() => setRuleEditor(null)}><X size={18} /></button></div>
          <label className="block text-sm">规则名称<input required maxLength={100} className={inputClass} value={ruleForm.name} onChange={event => setRuleForm({ ...ruleForm, name: event.target.value })} placeholder="例如：技术分类更新" /></label>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm">来源类型<select className={inputClass} value={ruleForm.source_type} onChange={event => setRuleForm({ ...ruleForm, source_type: event.target.value as SourceType, source_id: '' })}><option value="category">某个分类</option><option value="feed">某个 RSS</option></select></label>
            <label className="text-sm">推送来源<select required className={inputClass} value={ruleForm.source_id} onChange={event => setRuleForm({ ...ruleForm, source_id: event.target.value })}><option value="">请选择{ruleForm.source_type === 'feed' ? '订阅源' : '分类'}</option>{sourceOptions.map(source => <option key={source.id} value={source.id}>{source.name}</option>)}</select></label>
          </div>
          <fieldset className="space-y-2"><legend className="text-sm mb-2">发送到哪些频道（可多选）</legend><div className="flex flex-wrap gap-3">{channels.map(channel => <label key={channel.id} className="inline-flex gap-2 items-center text-sm rounded-lg bg-gray-50 dark:bg-gray-900 px-3 py-2">
            <input type="checkbox" checked={ruleForm.channel_ids.includes(channel.id)} onChange={event => setRuleForm({ ...ruleForm, channel_ids: event.target.checked ? [...ruleForm.channel_ids, channel.id] : ruleForm.channel_ids.filter(id => id !== channel.id) })} />{channel.name}{!channel.is_enabled && '（停用）'}</label>)}</div></fieldset>
          <label className="flex gap-2 text-sm"><input type="checkbox" checked={ruleForm.is_enabled} onChange={event => setRuleForm({ ...ruleForm, is_enabled: event.target.checked })} />启用规则</label>
          <div className="flex gap-2"><button className={primaryClass} disabled={saveRule.isPending || !ruleForm.channel_ids.length || !ruleForm.source_id}>{saveRule.isPending && <Loader2 size={16} className="animate-spin" />}保存规则</button><button type="button" className={buttonClass} onClick={() => setRuleEditor(null)}>取消</button></div>
        </form>}
        {rulesQuery.isLoading ? <p className="text-sm text-gray-500">加载规则中…</p> : rules.length === 0 ? <div className={`${panelClass} text-sm text-gray-500`}>暂无推送规则。选择一个分类或 RSS，即可自动发送更新。</div> : rules.map(rule => <div key={rule.id} className={`${panelClass} flex flex-wrap items-center justify-between gap-4`}>
          <div><h4 className="font-medium">{rule.name} <span className="text-xs text-gray-500">{rule.is_enabled ? '已启用' : '已停用'}</span></h4><p className="text-sm text-gray-500 mt-1">{rule.source_type === 'category' ? '分类' : 'RSS'}：{rule.source_name || '来源已删除'}</p><p className="text-sm text-gray-500 mt-1">发送到：{rule.channel_ids.map(id => channels.find(channel => channel.id === id)?.name).filter(Boolean).join('、') || '未绑定频道，请编辑规则'}</p></div>
          <div className="flex flex-wrap gap-2"><button className={buttonClass} onClick={() => openRule(rule)}><Edit2 size={15} />编辑</button><button className={buttonClass} disabled={toggleRule.isPending || !rule.channel_ids.length || !rule.source_name} onClick={() => toggleRule.mutate(rule)}>{rule.is_enabled ? '停用' : '启用'}</button><button className={`${buttonClass} text-red-600`} disabled={deleteRule.isPending} onClick={() => { if (confirm(`删除推送规则“${rule.name}”？`)) deleteRule.mutate(rule.id) }}><Trash2 size={15} />删除</button></div>
        </div>)}
      </div>}

      {section === 'history' && <div className="space-y-4">
        <p className="text-sm text-gray-500">“已发送”表示目标接口或邮件服务器已接受提交，实际接收请在目标应用确认。</p>
        <div className="flex items-center justify-between gap-3"><label className="text-sm">发送状态<select className={inputClass} value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="">全部状态</option>{Object.entries(statusNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button className={buttonClass} onClick={() => historyQuery.refetch()} disabled={historyQuery.isFetching}><RefreshCw size={15} />刷新记录</button></div>
        {historyQuery.isLoading ? <p className="text-sm text-gray-500">加载发送记录中…</p> : !historyQuery.data?.items.length ? <div className={`${panelClass} text-sm text-gray-500`}>暂无发送记录。频道测试和新文章推送都会在这里显示。</div> : historyQuery.data.items.map(delivery => <div key={delivery.id} className={panelClass}>
          <div className="flex justify-between gap-3"><h4 className="font-medium break-words">{delivery.is_test && <span className="mr-2 text-xs text-primary-600">测试</span>}{delivery.article_title}</h4><span className={`text-sm shrink-0 ${delivery.status === 'sent' ? 'text-green-600' : delivery.status === 'failed' ? 'text-red-600' : 'text-gray-500'}`}>{statusNames[delivery.status] || delivery.status}</span></div>
          <p className="text-xs text-gray-500 mt-2">{delivery.channel_name} · {providerNames[delivery.provider]} · {formatTime(delivery.created_at)} · 尝试 {delivery.attempts} 次</p>
          {delivery.error && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{delivery.error}</p>}
          {delivery.status === 'failed' && !delivery.is_test && <button className={`${buttonClass} mt-3`} disabled={retry.isPending} onClick={() => retry.mutate(delivery.id)}>重新发送</button>}
        </div>)}
        <div className="flex items-center justify-between text-sm text-gray-500"><span>共 {historyQuery.data?.total || 0} 条 · 第 {page} 页</span><div className="flex gap-2"><button className={buttonClass} disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</button><button className={buttonClass} disabled={!historyQuery.data || page * 20 >= historyQuery.data.total} onClick={() => setPage(page + 1)}>下一页</button></div></div>
      </div>}
    </div>
  )
}
