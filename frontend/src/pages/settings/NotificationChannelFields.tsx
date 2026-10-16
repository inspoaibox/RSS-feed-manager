import type { Dispatch, SetStateAction } from 'react'
import type { Channel, ChannelForm } from './notificationChannels'

const inputClass = 'block w-full mt-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-white'
const helpClass = 'text-xs text-gray-500 dark:text-gray-400'

interface Props {
  form: ChannelForm; setForm: Dispatch<SetStateAction<ChannelForm>>
  channel?: Channel; isNew: boolean
}

export default function NotificationChannelFields({ form, setForm, channel, isNew }: Props) {
  const change = (key: keyof ChannelForm, value: string | boolean) => setForm(current => ({ ...current, [key]: value }))
  const field = (label: string, key: keyof ChannelForm, placeholder = '', required = true, type = 'text', maxLength = 2048) => (
    <label className="block text-sm">{label}<input type={type} autoComplete={type === 'password' ? 'new-password' : 'off'}
      className={inputClass} required={required} maxLength={maxLength} value={String(form[key])}
      onChange={event => change(key, event.target.value)} placeholder={placeholder} /></label>
  )
  const secret = (label: string, key: keyof ChannelForm, saved: boolean | undefined, placeholder: string, required = true) => (
    field(label, key, saved ? '已保存，留空保持原值' : placeholder, required && (isNew || !saved), 'password')
  )

  if (form.provider === 'feishu') return <>
    {secret('Webhook 地址', 'webhook_url', channel?.has_webhook, 'https://open.feishu.cn/open-apis/bot/v2/hook/…')}
    {secret('签名密钥（可选）', 'signing_secret', channel?.has_signing_secret, '启用签名校验时填写', false)}
    {channel?.has_signing_secret && <label className="flex gap-2 text-sm"><input type="checkbox" checked={form.clear_signing_secret} onChange={event => change('clear_signing_secret', event.target.checked)} />清除已保存的签名密钥</label>}
    <p className={helpClass}>在群聊中添加自定义机器人，复制 Webhook。若设置了关键词验证，建议使用“RSS”；启用签名校验时填入机器人密钥。</p>
  </>
  if (form.provider === 'telegram') return <>
    {secret('Bot Token', 'bot_token', channel?.has_bot_token, '从 BotFather 获取')}
    <div className="grid gap-4 md:grid-cols-2">
      {field('Chat ID / 频道用户名', 'chat_id', '-1001234567890 或 @channel')}
      <label className="text-sm">话题 ID（可选）<input type="number" min={1} className={inputClass} value={form.message_thread_id} onChange={event => change('message_thread_id', event.target.value)} placeholder="用于群组话题" /></label>
    </div>
    <p className={helpClass}>把机器人加入群组或频道并授予发送消息权限；推送到个人聊天时，先向机器人发送 /start。</p>
  </>
  if (form.provider === 'wecom') return <>
    {secret('企业微信 Webhook 地址', 'webhook_url', channel?.has_webhook, 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=…')}
    <p className={helpClass}>在企业微信群的“消息推送”中添加机器人，复制 Webhook。消息发送到该企业微信群。</p>
  </>
  if (form.provider === 'email') return <>
    <div className="grid gap-4 md:grid-cols-2">
      {field('SMTP 主机', 'smtp_host', 'smtp.qq.com', true, 'text', 253)}
      <label className="text-sm">SMTP 端口<input required type="number" min={1} max={65535} className={inputClass} value={form.smtp_port} onChange={event => change('smtp_port', event.target.value)} /></label>
    </div>
    <label className="block text-sm">加密方式<select className={inputClass} value={form.smtp_security} onChange={event => setForm(current => ({ ...current,
      smtp_security: event.target.value,
      smtp_port: ['465', '587'].includes(current.smtp_port) ? (event.target.value === 'ssl' ? '465' : '587') : current.smtp_port,
    }))}><option value="ssl">SSL/TLS（通常为 465）</option><option value="starttls">STARTTLS（通常为 587）</option></select></label>
    {field('SMTP 用户名', 'smtp_username', '通常为完整邮箱地址', true, 'text', 320)}
    {secret('SMTP 密码 / 授权码', 'smtp_password', channel?.has_smtp_password, '填写邮箱授权码或 SMTP 密码')}
    {field('发件邮箱', 'smtp_from', 'notify@example.com', true, 'email', 320)}
    <label className="block text-sm">收件邮箱<textarea required rows={2} className={inputClass} value={form.smtp_to} onChange={event => change('smtp_to', event.target.value)} placeholder="多个地址用逗号或换行分隔，最多 20 个" /></label>
    <p className={helpClass}>先在邮箱服务中启用 SMTP。用户名及密码 / 授权码仅支持 ASCII 字符，QQ、163 等邮箱通常需要使用授权码；请按邮箱服务商要求选择加密方式和端口。</p>
  </>
  if (form.provider === 'bark') return <>
    {secret('Device Key', 'device_key', channel?.has_device_key, '从 Bark App 推送地址中复制 Key')}
    {secret('Bark 服务器（可选）', 'server_url', channel?.has_server_url, '默认 https://api.day.app；也可填写自建 HTTPS 地址', false)}
    {field('通知分组', 'bark_group', 'RSS', false, 'text', 100)}
    <p className={helpClass}>在 iPhone 上安装 Bark，填写 Device Key。只填写密钥，不要粘贴完整的推送地址。</p>
  </>
  if (form.provider === 'pushplus') return <>
    {secret('PushPlus Token', 'pushplus_token', channel?.has_pushplus_token, '从 PushPlus 个人中心获取')}
    <label className="block text-sm">接收渠道<select className={inputClass} value={form.pushplus_channel} onChange={event => change('pushplus_channel', event.target.value)}>
      <option value="wechat">微信公众号</option><option value="app">PushPlus App</option><option value="mail">邮件</option><option value="webhook">第三方 Webhook</option><option value="cp">企业微信应用</option><option value="extension">浏览器 / 桌面插件</option><option value="qq">QQ 机器人</option>
    </select></label>
    {field('群组编码（可选）', 'pushplus_topic', '留空发送给自己', false, 'text', 100)}
    {field('渠道编码', 'pushplus_option', '在 PushPlus 后台创建的渠道编码', ['mail', 'webhook', 'cp'].includes(form.pushplus_channel), 'text', 100)}
    <p className={helpClass}>先在 PushPlus 绑定接收通道并完成服务要求的实名认证。接口提交成功表示平台已接受请求，实际接收请在对应应用确认。</p>
  </>
  if (form.provider === 'serverchan') return <>
    {secret('SendKey', 'serverchan_send_key', channel?.has_serverchan_send_key, 'SCT…、sctp… 或 sc3…')}
    <p className={helpClass}>在 Server酱 Turbo 或 Server酱³ 中获取 SendKey，并在服务侧绑定微信或 App 接收通道；系统会自动选择对应版本的接口。</p>
  </>
  return <>
    {secret('Webhook 地址', 'webhook_url', channel?.has_webhook, 'https://example.com/notify')}
    <label className="block text-sm">请求方法<select className={inputClass} value={form.webhook_method} onChange={event => change('webhook_method', event.target.value)}><option value="POST">POST</option><option value="PUT">PUT</option></select></label>
    <label className="block text-sm">请求头 JSON（可选）<textarea rows={3} maxLength={90000} autoComplete="off" className={`${inputClass} font-mono`} value={form.webhook_headers} disabled={form.clear_webhook_headers} onChange={event => change('webhook_headers', event.target.value)} placeholder={channel?.has_webhook_headers ? '已保存，留空保持原值' : '{"Authorization": "Bearer your-token"}'} /></label>
    {channel?.has_webhook_headers && <label className="flex gap-2 text-sm"><input type="checkbox" checked={form.clear_webhook_headers} onChange={event => change('clear_webhook_headers', event.target.checked)} />清除已保存的请求头</label>}
    <label className="block text-sm">请求体 JSON 模板（可选）<textarea rows={4} maxLength={20000} autoComplete="off" className={`${inputClass} font-mono`} value={form.webhook_body} disabled={form.clear_webhook_body} onChange={event => change('webhook_body', event.target.value)} placeholder={channel?.has_webhook_body ? '已保存，留空保持原值' : '{"title": "{{title}}", "message": "{{message}}"}'} /></label>
    {channel?.has_webhook_body && <label className="flex gap-2 text-sm"><input type="checkbox" checked={form.clear_webhook_body} onChange={event => change('clear_webhook_body', event.target.checked)} />恢复默认请求体</label>}
    <p className={helpClass}>{'填写 HTTPS 接口。模板字符串值支持 {{title}}（文章标题）和 {{message}}（含来源、时间和原文链接的通知正文），支持嵌套 JSON。目标返回 2xx 表示接受请求。'}</p>
  </>
}
