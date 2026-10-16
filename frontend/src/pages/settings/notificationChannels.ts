export type Provider = 'feishu' | 'telegram' | 'wecom' | 'email' | 'bark' | 'pushplus' | 'serverchan' | 'webhook'

export interface Channel {
  id: number; name: string; provider: Provider; is_enabled: boolean
  has_webhook: boolean; has_signing_secret: boolean; has_bot_token: boolean
  chat_id: string | null; message_thread_id: number | null
  has_server_url: boolean; has_device_key: boolean; has_pushplus_token: boolean
  has_serverchan_send_key: boolean; has_smtp_password: boolean
  has_webhook_headers: boolean; has_webhook_body: boolean
  bark_group: string | null; pushplus_channel: string | null
  pushplus_topic: string | null; pushplus_option: string | null
  smtp_host: string | null; smtp_port: number | null; smtp_security: string | null
  smtp_username: string | null; smtp_from: string | null; smtp_to: string[]
  webhook_method: string | null
}

export const providerNames: Record<Provider, string> = {
  feishu: '飞书 / Lark', telegram: 'Telegram', wecom: '企业微信', email: '邮件 SMTP',
  bark: 'Bark', pushplus: 'PushPlus', serverchan: 'Server酱', webhook: '通用 Webhook',
}

export const emptyChannel = {
  name: '', provider: 'feishu' as Provider, is_enabled: true,
  webhook_url: '', signing_secret: '', bot_token: '', chat_id: '', message_thread_id: '',
  server_url: '', device_key: '', bark_group: 'RSS', pushplus_token: '',
  pushplus_channel: 'wechat', pushplus_topic: '', pushplus_option: '', serverchan_send_key: '',
  smtp_host: '', smtp_port: '465', smtp_security: 'ssl', smtp_username: '', smtp_password: '',
  smtp_from: '', smtp_to: '', webhook_method: 'POST', webhook_headers: '', webhook_body: '',
  clear_signing_secret: false, clear_webhook_headers: false, clear_webhook_body: false,
}
export type ChannelForm = typeof emptyChannel

export class ChannelConfigError extends Error {}

function jsonObject(value: string, headers = false): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(value)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error()
    if (headers && Object.values(parsed).some(item => typeof item !== 'string')) throw new Error()
    return parsed as Record<string, unknown>
  } catch {
    throw new ChannelConfigError(headers ? '请求头必须是值为字符串的 JSON 对象' : '请求体模板必须是有效的 JSON 对象')
  }
}

export function channelConfig(form: ChannelForm, isNew: boolean) {
  switch (form.provider) {
    case 'feishu': return {
      webhook_url: form.webhook_url,
      signing_secret: form.clear_signing_secret ? null : form.signing_secret,
    }
    case 'telegram': return {
      bot_token: form.bot_token, chat_id: form.chat_id,
      message_thread_id: form.message_thread_id ? Number(form.message_thread_id) : null,
    }
    case 'wecom': return { webhook_url: form.webhook_url }
    case 'email': return {
      smtp_host: form.smtp_host, smtp_port: Number(form.smtp_port), smtp_security: form.smtp_security,
      smtp_username: form.smtp_username, smtp_password: form.smtp_password,
      smtp_from: form.smtp_from,
      smtp_to: form.smtp_to.split(/[,;\n，；]+/).map(value => value.trim()).filter(Boolean),
    }
    case 'bark': return { server_url: form.server_url, device_key: form.device_key, bark_group: form.bark_group }
    case 'pushplus': return {
      pushplus_token: form.pushplus_token, pushplus_channel: form.pushplus_channel,
      pushplus_topic: form.pushplus_topic, pushplus_option: form.pushplus_option,
    }
    case 'serverchan': return { serverchan_send_key: form.serverchan_send_key }
    case 'webhook': return {
      webhook_url: form.webhook_url, webhook_method: form.webhook_method,
      ...(form.clear_webhook_headers ? { webhook_headers: null }
        : form.webhook_headers.trim() ? { webhook_headers: jsonObject(form.webhook_headers, true) }
        : isNew ? { webhook_headers: {} } : {}),
      ...(form.clear_webhook_body ? { webhook_body: null }
        : form.webhook_body.trim() ? { webhook_body: jsonObject(form.webhook_body) }
        : isNew ? { webhook_body: null } : {}),
    }
  }
}

export function channelFormFor(channel?: Channel): ChannelForm {
  if (!channel) return { ...emptyChannel }
  return {
    ...emptyChannel, name: channel.name, provider: channel.provider, is_enabled: channel.is_enabled,
    chat_id: channel.chat_id || '', message_thread_id: String(channel.message_thread_id || ''),
    bark_group: channel.bark_group || 'RSS', pushplus_channel: channel.pushplus_channel || 'wechat',
    pushplus_topic: channel.pushplus_topic || '', pushplus_option: channel.pushplus_option || '',
    smtp_host: channel.smtp_host || '', smtp_port: String(channel.smtp_port || 465),
    smtp_security: channel.smtp_security || 'ssl', smtp_username: channel.smtp_username || '',
    smtp_from: channel.smtp_from || '', smtp_to: (channel.smtp_to || []).join(', '),
    webhook_method: channel.webhook_method || 'POST',
  }
}
