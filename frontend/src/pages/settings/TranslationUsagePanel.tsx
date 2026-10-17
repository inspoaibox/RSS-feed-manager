import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '@/services/api'
import { getApiErrorMessage } from '@/utils/apiError'

type Limits = {
  translation_max_input_tokens: number
  translation_max_output_tokens: number
  translation_article_token_limit: number
  translation_monthly_token_limit: number | null
  translation_max_requests: number
}
type Receipt = {
  id: number; article_id: number | null; model: string; status: string
  input_tokens: number | null; output_tokens: number | null; total_tokens: number | null
  budget_tokens: number; created_at: string; error: string | null
}
type Usage = {
  reported_tokens: number; budget_tokens: number; requests: number; unreported_requests: number
  items: Receipt[]; total: number; page: number; page_size: number
}
const fields = [
  ['translation_max_input_tokens', '单次输入预算（估算 token）', 128, 100000],
  ['translation_max_output_tokens', '单次输出 token 上限', 128, 32768],
  ['translation_article_token_limit', '单篇累计 token 预算', 1000, 10000000],
  ['translation_max_requests', '单篇累计请求次数上限', 1, 1000],
] as const
const labels: Record<string, string> = {
  pending: '等待用量回执', succeeded: '完成', truncated: '输出截断', unknown: '结果待核对', rejected: '请求被拒绝',
}

export default function TranslationUsagePanel() {
  const client = useQueryClient()
  const [page, setPage] = useState(1)
  const [limits, setLimits] = useState<Limits | null>(null)
  const settings = useQuery({ queryKey: ['ai-settings'], queryFn: async () => (await api.get<Limits>('/ai/settings')).data })
  const usage = useQuery({ queryKey: ['translation-usage', page], queryFn: async () =>
    (await api.get<Usage>('/ai/translation-usage', { params: { page, page_size: 10 } })).data,
    refetchInterval: 15000,
  })
  useEffect(() => {
    if (settings.data) setLimits(settings.data)
  }, [settings.data])
  const save = useMutation({
    mutationFn: async () => {
      if (!limits) return
      const payload = Object.fromEntries([...fields.map(([key]) => [key, limits[key]]),
        ['translation_monthly_token_limit', limits.translation_monthly_token_limit]])
      await api.put('/ai/settings', payload)
    },
    onSuccess: () => { client.invalidateQueries({ queryKey: ['ai-settings'] }) },
  })
  const error = save.error || settings.error || usage.error
  return (
    <section className="p-4 border border-gray-200 dark:border-gray-700 rounded space-y-4">
      <h2 className="text-lg font-semibold dark:text-white">AI 翻译用量与限额</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        统计本系统的 AI 翻译和模型翻译测试，按 UTC 自然月汇总。整理、分析和 Embedding 不计入此处。
        发送前预留预算，收到用量回执后按实际 token 更新；缺少回执的请求保留估算额度，实际费用以服务商账单为准。
      </p>
      {error && <p role="alert" className="text-sm text-red-600">{getApiErrorMessage(error, '读取或保存失败')}</p>}
      {usage.data && (
        <div className="grid gap-3 sm:grid-cols-3 text-sm dark:text-gray-200">
          <p>本月已报告用量 <strong>{usage.data.reported_tokens.toLocaleString()}</strong> token</p>
          <p>本月预算占用 <strong>{usage.data.budget_tokens.toLocaleString()}</strong> token</p>
          <p>缺少用量回执 <strong>{usage.data.unreported_requests}</strong> 次</p>
        </div>
      )}
      {limits && (
        <form onSubmit={event => { event.preventDefault(); save.mutate() }} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {fields.map(([key, label, min, max]) => (
              <label key={key} className="text-sm text-gray-700 dark:text-gray-300">
                {label}
                <input type="number" required min={min} max={max} step={1} value={Number.isNaN(limits[key]) ? '' : limits[key] ?? ''}
                  onChange={event => setLimits({ ...limits, [key]: event.target.value === '' ? NaN : Number(event.target.value) })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800" />
              </label>
            ))}
            <label className="text-sm text-gray-700 dark:text-gray-300">
              每月累计 token 预算（留空不设限）
              <input type="number" min={1} max={2000000000} step={1} value={limits.translation_monthly_token_limit ?? ''}
                onChange={event => setLimits({ ...limits, translation_monthly_token_limit: event.target.value ? Number(event.target.value) : null })}
                className="mt-1 block w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800" />
            </label>
          </div>
          <p className="text-xs text-gray-500">缓存与推理 token 已包含在服务商总量中，不重复相加。达到预算时暂停发送并保留已完成的分段。</p>
          <button disabled={save.isPending} className="px-4 py-2 bg-primary-600 text-white rounded disabled:opacity-50">保存翻译限额</button>
          {save.isSuccess && <span role="status" className="ml-3 text-sm text-green-600">翻译限额已保存</span>}
        </form>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left dark:text-gray-300">
          <thead><tr className="border-b border-gray-200 dark:border-gray-700">
            <th className="p-2">时间 / 文章</th><th className="p-2">模型</th><th className="p-2">状态</th>
            <th className="p-2">输入 / 输出</th><th className="p-2">实际总量</th><th className="p-2">预算占用</th>
          </tr></thead>
          <tbody>{usage.data?.items.map(row => (
            <tr key={row.id} className="border-b border-gray-200 dark:border-gray-700">
              <td className="p-2">{new Date(row.created_at.endsWith('Z') || /[+-]\d\d:\d\d$/.test(row.created_at) ? row.created_at : `${row.created_at}Z`).toLocaleString()}<br />{row.article_id ? `文章 #${row.article_id}` : '模型测试'}</td>
              <td className="p-2 break-all">{row.model}</td><td className="p-2" title={row.error || ''}>{labels[row.status] || row.status}</td>
              <td className="p-2">{row.input_tokens ?? '—'} / {row.output_tokens ?? '—'}</td>
              <td className="p-2">{row.total_tokens ?? '未返回'}</td><td className="p-2">{row.budget_tokens}</td>
            </tr>
          ))}</tbody>
        </table>
        {usage.data?.total === 0 && <p className="py-3 text-sm text-gray-500">暂无翻译用量记录；历史请求不会追溯计入。</p>}
      </div>
      <div className="flex gap-3 items-center text-sm dark:text-gray-300">
        <button className="border rounded px-2 py-1 disabled:opacity-50" disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</button>
        <span>第 {page} 页</span>
        <button className="border rounded px-2 py-1 disabled:opacity-50" disabled={!usage.data || page * 10 >= usage.data.total} onClick={() => setPage(page + 1)}>下一页</button>
      </div>
    </section>
  )
}
