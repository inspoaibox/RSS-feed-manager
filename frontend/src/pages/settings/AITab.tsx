import { AIModelFormState,AIProviderFormState,createEmptyAIModelForm,createEmptyAIProviderForm,formatDateTime,formatDurationMs,getArgosLogStatusClass,getArgosLogStatusLabel,getTranslationLanguageLabel,translationSourceLanguages } from '@/pages/settings/shared'
import api from '@/services/api'
import type { AIModel,AIProvider,ArgosPackageInfo,ArgosPackagesResponse,ArgosPackageTestResult,ArgosTranslationLogsResponse,GoogleTranslateKey } from '@/types'
import { getApiErrorMessage } from '@/utils/apiError'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { Check,Download,Edit2,History,Languages,Plus,RefreshCw,Trash2,X } from 'lucide-react'
import { useMemo,useState } from 'react'

export default function AITab() {
  const queryClient = useQueryClient()
  const [showProviderForm, setShowProviderForm] = useState(false)
  const [editingProviderId, setEditingProviderId] = useState<number | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [providerForm, setProviderForm] = useState<AIProviderFormState>(createEmptyAIProviderForm())
  const [providerModelForm, setProviderModelForm] = useState<AIModelFormState>(createEmptyAIModelForm())
  const [prompts, setPrompts] = useState({
    translate: '',
    summarize: '',
  })
  const [promptSettingsLoaded, setPromptSettingsLoaded] = useState(false)
  const [autoGenerateSummaries, setAutoGenerateSummaries] = useState(false)
  const [newGoogleKey, setNewGoogleKey] = useState({
    name: '',
    api_key: '',
    is_active: true,
    limit_days: '',
    limit_articles: '',
    limit_characters: '',
  })
  const [editingGoogleKeyId, setEditingGoogleKeyId] = useState<number | null>(null)
  const [googleKeyEdit, setGoogleKeyEdit] = useState({
    name: '',
    api_key: '',
    is_active: true,
    limit_days: '',
    limit_articles: '',
    limit_characters: '',
  })
  const [argosLogPage, setArgosLogPage] = useState(1)
  const [showArgosLogsModal, setShowArgosLogsModal] = useState(false)
  const argosLogPageSize = 10

  const { data: providers = [] } = useQuery({
    queryKey: ['ai-providers'],
    queryFn: async () => {
      const response = await api.get<AIProvider[]>('/ai/providers')
      return response.data
    },
  })

  const { data: models = [] } = useQuery({
    queryKey: ['ai-models'],
    queryFn: async () => {
      const response = await api.get<AIModel[]>('/ai/models')
      return response.data
    },
  })
  const editingProvider = useMemo(
    () => providers.find((provider) => provider.id === editingProviderId) ?? null,
    [providers, editingProviderId]
  )
  const editingProviderModels = useMemo(
    () => (editingProviderId === null ? [] : models.filter((model) => model.provider_id === editingProviderId)),
    [models, editingProviderId]
  )
  const isEditingProvider = editingProviderId !== null

  const { data: settings } = useQuery({
    queryKey: ['ai-settings'],
    queryFn: async () => {
      const response = await api.get<{
        translate_prompt: string
        summarize_prompt: string
        auto_generate_summaries: boolean
        embedding_provider_id: number | null
        embedding_model: string | null
        auto_generate_embeddings: boolean
        argos_source_language: string | null
        mc_translation_api_key: string | null
        mc_translation_base_url: string | null
        mc_translation_model: string | null
      }>('/ai/settings')
      return response.data
    },
  })

  const { data: googleTranslateKeys = [] } = useQuery({
    queryKey: ['google-translate-keys'],
    queryFn: async () => {
      const response = await api.get<GoogleTranslateKey[]>('/ai/google-translate-keys')
      return response.data
    },
  })

  const { data: argosPackages, isLoading: argosPackagesLoading, error: argosPackagesError } = useQuery<ArgosPackagesResponse>({
    queryKey: ['argos-packages'],
    queryFn: async () => {
      const response = await api.get<ArgosPackagesResponse>('/ai/argos/packages')
      return response.data
    },
    retry: false,
  })

  const { data: argosTranslationLogs, isLoading: argosLogsLoading } = useQuery<ArgosTranslationLogsResponse>({
    queryKey: ['argos-translation-logs', argosLogPage],
    queryFn: async () => {
      const response = await api.get<ArgosTranslationLogsResponse>('/ai/argos/translation-logs', {
        params: { page: argosLogPage, page_size: argosLogPageSize },
      })
      return response.data
    },
    enabled: showArgosLogsModal,
    refetchInterval: showArgosLogsModal ? 10000 : false,
  })

  const [embeddingConfig, setEmbeddingConfig] = useState<{
    provider_id: number | null
    model: string
    auto_generate: boolean
  }>({ provider_id: null, model: '', auto_generate: false })
  const [embeddingSettingsLoaded, setEmbeddingSettingsLoaded] = useState(false)
  const [argosSourceLanguage, setArgosSourceLanguage] = useState('en')
  const [argosSettingsLoaded, setArgosSettingsLoaded] = useState(false)
  const [argosInstallForm, setArgosInstallForm] = useState({
    source_language: 'en',
    target_language: 'zh',
  })
  const [argosTestForm, setArgosTestForm] = useState({
    source_language: 'en',
    target_language: 'zh',
    text: 'Hello world',
  })
  const [argosTestResult, setArgosTestResult] = useState<ArgosPackageTestResult | null>(null)
  const [mcTranslationConfig, setMcTranslationConfig] = useState({
    api_key: '',
    base_url: 'https://fanyi.aboen.com',
    model: 'argos',
  })
  const [mcTranslationLoaded, setMcTranslationLoaded] = useState(false)
  const [mcTranslationTestResult, setMcTranslationTestResult] = useState<{
    success: boolean
    message: string
    translation: string | null
  } | null>(null)

  const buildGoogleKeyPayload = (form: typeof newGoogleKey, includeApiKey: boolean) => ({
    name: form.name.trim(),
    ...(includeApiKey && form.api_key.trim() ? { api_key: form.api_key.trim() } : {}),
    is_active: form.is_active,
    limit_days: form.limit_days ? parseInt(form.limit_days) : null,
    limit_articles: form.limit_articles ? parseInt(form.limit_articles) : null,
    limit_characters: form.limit_characters ? parseInt(form.limit_characters) : null,
  })

  // Initialize prompts and embedding config when settings load
  if (settings && !promptSettingsLoaded) {
    setPrompts({
      translate: settings.translate_prompt,
      summarize: settings.summarize_prompt,
    })
    setAutoGenerateSummaries(settings.auto_generate_summaries || false)
    setPromptSettingsLoaded(true)
  }
  
  // Initialize embedding config when settings load
  if (settings && !embeddingSettingsLoaded) {
    setEmbeddingConfig({
      provider_id: settings.embedding_provider_id,
      model: settings.embedding_model || '',
      auto_generate: settings.auto_generate_embeddings || false,
    })
    setEmbeddingSettingsLoaded(true)
  }

  if (settings && !argosSettingsLoaded) {
    setArgosSourceLanguage(settings.argos_source_language || 'en')
    setArgosSettingsLoaded(true)
  }

  if (settings && !mcTranslationLoaded) {
    setMcTranslationConfig({
      api_key: settings.mc_translation_api_key || '',
      base_url: settings.mc_translation_base_url || 'https://fanyi.aboen.com',
      model: settings.mc_translation_model || 'argos',
    })
    setMcTranslationLoaded(true)
  }
  const resetProviderForm = () => {
    setProviderForm(createEmptyAIProviderForm())
    setProviderModelForm(createEmptyAIModelForm())
    setEditingProviderId(null)
  }

  const closeProviderForm = () => {
    resetProviderForm()
    setShowProviderForm(false)
  }

  const openCreateProviderForm = () => {
    resetProviderForm()
    setShowProviderForm(true)
  }

  const openEditProviderForm = (provider: AIProvider) => {
    setEditingProviderId(provider.id)
    setProviderForm({
      name: provider.name,
      type: provider.type,
      api_key: '',
      base_url: provider.base_url || '',
    })
    setProviderModelForm(createEmptyAIModelForm())
    setShowProviderForm(true)
  }

  const addProviderMutation = useMutation({
    mutationFn: async (payload: AIProviderFormState) => {
      const response = await api.post<AIProvider>('/ai/providers', {
        name: payload.name.trim(),
        type: payload.type,
        api_key: payload.api_key.trim(),
        base_url: payload.base_url.trim() || undefined,
      })
      return response.data
    },
    onSuccess: (provider) => {
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] })
      setEditingProviderId(provider.id)
      setShowProviderForm(true)
      setProviderForm({
        name: provider.name,
        type: provider.type,
        api_key: '',
        base_url: provider.base_url || '',
      })
      setProviderModelForm(createEmptyAIModelForm())
      setMessage({ type: 'success', text: '渠道添加成功，可继续在此获取所有模型' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '添加失败') })
    },
  })

  const updateProviderMutation = useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: AIProviderFormState }) => {
      const response = await api.put<AIProvider>(`/ai/providers/${id}`, {
        name: payload.name.trim(),
        api_key: payload.api_key.trim() || undefined,
        base_url: payload.base_url.trim(),
      })
      return response.data
    },
    onSuccess: (provider) => {
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] })
      setEditingProviderId(provider.id)
      setProviderForm({
        name: provider.name,
        type: provider.type,
        api_key: '',
        base_url: provider.base_url || '',
      })
      setProviderModelForm(createEmptyAIModelForm())
      setMessage({ type: 'success', text: '渠道已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '更新失败') })
    },
  })

  const deleteProviderMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/ai/providers/${id}`)
    },
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] })
      queryClient.invalidateQueries({ queryKey: ['ai-models'] })
      if (editingProviderId === deletedId) {
        closeProviderForm()
      }
      setMessage({ type: 'success', text: '渠道已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '删除渠道失败') })
    },
  })

  const setDefaultModelMutation = useMutation({
    mutationFn: async (modelId: number) => {
      await api.put(`/ai/models/${modelId}/default`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-models'] })
      setMessage({ type: 'success', text: '默认模型已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
  })

  const fetchModelsMutation = useMutation({
    mutationFn: async (providerId: number) => {
      await api.post(`/ai/providers/${providerId}/fetch-models`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] })
      queryClient.invalidateQueries({ queryKey: ['ai-models'] })
      setMessage({ type: 'success', text: '模型列表已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '获取模型失败') })
    },
  })

  const testProviderMutation = useMutation({
    mutationFn: async (providerId: number) => {
      const response = await api.post<{ success: boolean; message: string }>(`/ai/providers/${providerId}/test`)
      return response.data
    },
    onSuccess: (result) => {
      setMessage({
        type: result.success ? 'success' : 'error',
        text: result.success ? '连接测试成功' : `连接测试失败: ${result.message}`,
      })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '连接测试失败') })
    },
  })

  const createModelMutation = useMutation({
    mutationFn: async ({ providerId, payload }: { providerId: number; payload: AIModelFormState }) => {
      await api.post(`/ai/providers/${providerId}/models`, {
        model_id: payload.model_id.trim(),
        name: payload.name.trim() || payload.model_id.trim(),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] })
      queryClient.invalidateQueries({ queryKey: ['ai-models'] })
      setProviderModelForm(createEmptyAIModelForm())
      setMessage({ type: 'success', text: '模型已添加' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '添加模型失败') })
    },
  })

  const isSavingProvider = addProviderMutation.isPending || updateProviderMutation.isPending
  const normalizedProviderBaseUrl = providerForm.base_url.trim()
  const providerNeedsBaseUrl = providerForm.type === 'openai_compatible'
  const hasValidProviderBaseUrl = !providerNeedsBaseUrl || /^https?:\/\/\S+$/i.test(normalizedProviderBaseUrl)
  const canSubmitProvider = (
    providerForm.name.trim() !== ''
    && (isEditingProvider || providerForm.api_key.trim() !== '')
    && hasValidProviderBaseUrl
  )
  const canManageProviderModels = editingProviderId !== null && !isSavingProvider
  const canCreateModel = canManageProviderModels && providerModelForm.model_id.trim() !== ''

  const submitProviderForm = () => {
    if (!canSubmitProvider) return
    if (isEditingProvider && editingProviderId !== null) {
      updateProviderMutation.mutate({ id: editingProviderId, payload: providerForm })
      return
    }
    addProviderMutation.mutate(providerForm)
  }

  const submitProviderModelForm = () => {
    if (editingProviderId === null || !canCreateModel) return
    createModelMutation.mutate({
      providerId: editingProviderId,
      payload: providerModelForm,
    })
  }

  const savePromptsMutation = useMutation({
    mutationFn: async () => {
      await api.put('/ai/settings', {
        translate_prompt: prompts.translate,
        summarize_prompt: prompts.summarize,
        auto_generate_summaries: autoGenerateSummaries,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
      setMessage({ type: 'success', text: 'Prompt 已保存' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '保存失败') })
    },
  })

  const saveEmbeddingConfigMutation = useMutation({
    mutationFn: async () => {
      await api.put('/ai/settings', {
        embedding_provider_id: embeddingConfig.provider_id,
        embedding_model: embeddingConfig.model || null,
        auto_generate_embeddings: embeddingConfig.auto_generate,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
      setMessage({ type: 'success', text: 'Embedding 模型已保存' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '保存失败') })
    },
  })

  const saveArgosConfigMutation = useMutation({
    mutationFn: async () => {
      await api.put('/ai/settings', {
        argos_source_language: argosSourceLanguage || 'en',
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
      setMessage({ type: 'success', text: '本地翻译设置已保存' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '保存失败') })
    },
  })

  const saveMcTranslationConfigMutation = useMutation({
    mutationFn: async () => {
      await api.put('/ai/settings', {
        mc_translation_api_key: mcTranslationConfig.api_key.trim() || null,
        mc_translation_base_url: mcTranslationConfig.base_url.trim() || 'https://fanyi.aboen.com',
        mc_translation_model: mcTranslationConfig.model.trim() || 'argos',
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
      setMessage({ type: 'success', text: 'Mc-Translation 设置已保存' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '保存失败') })
    },
  })

  const testMcTranslationMutation = useMutation({
    mutationFn: async () => {
      await api.put('/ai/settings', {
        mc_translation_api_key: mcTranslationConfig.api_key.trim() || null,
        mc_translation_base_url: mcTranslationConfig.base_url.trim() || 'https://fanyi.aboen.com',
        mc_translation_model: mcTranslationConfig.model.trim() || 'argos',
      })
      const response = await api.post<{ success: boolean; message: string; translation: string | null }>('/ai/mc-translation/test')
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
      setMcTranslationTestResult(data)
      setMessage({ type: data.success ? 'success' : 'error', text: data.message })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMcTranslationTestResult(null)
      setMessage({ type: 'error', text: getApiErrorMessage(err, 'Mc-Translation 测试失败') })
    },
  })

  const refreshArgosPackagesMutation = useMutation({
    mutationFn: async () => {
      const response = await api.get<ArgosPackagesResponse>('/ai/argos/packages', {
        params: { refresh: true },
      })
      return response.data
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['argos-packages'], data)
      setMessage({
        type: data.available_error ? 'error' : 'success',
        text: data.available_error || 'Argos 语言包列表已刷新',
      })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '刷新语言包列表失败') })
    },
  })

  const installArgosPackageMutation = useMutation({
    mutationFn: async (payload?: { source_language: string; target_language: string }) => {
      const response = await api.post<ArgosPackageInfo>('/ai/argos/packages/install', payload || argosInstallForm)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['argos-packages'] })
      setMessage({
        type: 'success',
        text: `Argos 语言包已安装: ${data.source_language} -> ${data.target_language}`,
      })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '安装语言包失败') })
    },
  })

  const uninstallArgosPackageMutation = useMutation({
    mutationFn: async (pkg: ArgosPackageInfo) => {
      const response = await api.delete<{ success: boolean; message: string }>(
        `/ai/argos/packages/${encodeURIComponent(pkg.source_language)}/${encodeURIComponent(pkg.target_language)}`
      )
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['argos-packages'] })
      setMessage({ type: 'success', text: data.message })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '卸载语言包失败') })
    },
  })

  const testArgosPackageMutation = useMutation({
    mutationFn: async (payload?: { source_language: string; target_language: string; text?: string }) => {
      const response = await api.post<ArgosPackageTestResult>('/ai/argos/test', {
        source_language: payload?.source_language || argosTestForm.source_language,
        target_language: payload?.target_language || argosTestForm.target_language,
        text: payload?.text || argosTestForm.text,
      })
      return response.data
    },
    onSuccess: (data) => {
      setArgosTestResult(data)
      setMessage({ type: data.success ? 'success' : 'error', text: data.message })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setArgosTestResult(null)
      setMessage({ type: 'error', text: getApiErrorMessage(err, '测试语言包失败') })
    },
  })

  const clearArgosLogsMutation = useMutation({
    mutationFn: async () => {
      const response = await api.delete<{ success: boolean; deleted: number }>('/ai/argos/translation-logs')
      return response.data
    },
    onSuccess: (data) => {
      setArgosLogPage(1)
      queryClient.invalidateQueries({ queryKey: ['argos-translation-logs'] })
      setMessage({ type: 'success', text: `已清除 ${data.deleted} 条本地翻译记录` })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '清除本地翻译记录失败') })
    },
  })

  const addGoogleKeyMutation = useMutation({
    mutationFn: async () => {
      await api.post('/ai/google-translate-keys', buildGoogleKeyPayload(newGoogleKey, true))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setNewGoogleKey({
        name: '',
        api_key: '',
        is_active: true,
        limit_days: '',
        limit_articles: '',
        limit_characters: '',
      })
      setMessage({ type: 'success', text: 'Google API Key 已添加' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '添加失败') })
    },
  })

  const updateGoogleKeyMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: typeof googleKeyEdit }) => {
      await api.put(`/ai/google-translate-keys/${id}`, buildGoogleKeyPayload(data, true))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setEditingGoogleKeyId(null)
      setMessage({ type: 'success', text: 'Google API Key 已更新' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '更新失败') })
    },
  })

  const deleteGoogleKeyMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/ai/google-translate-keys/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setMessage({ type: 'success', text: 'Google API Key 已删除' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '删除失败') })
    },
  })

  const resetGoogleKeyMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/ai/google-translate-keys/${id}/reset`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setMessage({ type: 'success', text: 'Google API Key 用量已重置' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '重置失败') })
    },
  })

  const testGoogleKeyMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.post<{ success: boolean; message: string }>(`/ai/google-translate-keys/${id}/test`)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['google-translate-keys'] })
      setMessage({ type: data.success ? 'success' : 'error', text: data.message })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setMessage({ type: 'error', text: getApiErrorMessage(err, '测试失败') })
    },
  })

  const defaultModel = models.find(m => m.is_default)
  const activeGoogleKeyCount = googleTranslateKeys.filter((key) => key.is_active).length
  const installedArgosPackages = argosPackages?.installed || []
  const availableArgosPackages = argosPackages?.available || []
  const argosLogs = argosTranslationLogs?.items || []
  const argosLogTotal = argosTranslationLogs?.total || 0
  const argosLogTotalPages = argosTranslationLogs?.total_pages || 1
  const visibleAvailableArgosPackages = availableArgosPackages
    .filter((pkg) => !pkg.installed)
    .slice(0, 12)
  const selectedInstallPackageInstalled = installedArgosPackages.some(
    (pkg) =>
      pkg.source_language === argosInstallForm.source_language &&
      pkg.target_language === argosInstallForm.target_language
  )
  const argosPackagesErrorText = argosPackagesError
    ? getApiErrorMessage(argosPackagesError, '本地翻译语言包读取失败')
    : null

  const startGoogleKeyEdit = (key: GoogleTranslateKey) => {
    setEditingGoogleKeyId(key.id)
    setGoogleKeyEdit({
      name: key.name,
      api_key: '',
      is_active: key.is_active,
      limit_days: key.limit_days?.toString() || '',
      limit_articles: key.limit_articles?.toString() || '',
      limit_characters: key.limit_characters?.toString() || '',
    })
  }

  return (
    <div className="space-y-6">
      {message && (
        <div className={`p-3 rounded ${message.type === 'success' ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
          {message.text}
        </div>
      )}

      {/* Default Model Selection */}
      <div className="p-4 border dark:border-gray-700 rounded bg-primary-50 dark:bg-primary-900/30">
        <h2 className="text-lg font-semibold mb-3 dark:text-white">默认模型</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">用于 AI 翻译、整理和分析总结</p>
        <select
          value={defaultModel?.id || ''}
          onChange={(e) => e.target.value && setDefaultModelMutation.mutate(parseInt(e.target.value))}
          className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
          disabled={models.length === 0}
        >
          <option value="">请选择默认模型</option>
          {providers.map(provider => {
            const providerModels = models.filter(m => m.provider_id === provider.id)
            if (providerModels.length === 0) return null
            return (
              <optgroup key={provider.id} label={provider.name}>
                {providerModels.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.model_id}
                  </option>
                ))}
              </optgroup>
            )
          })}
        </select>
        {models.length === 0 && (
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">请先添加 AI 渠道，并在渠道表单中获取所有模型</p>
        )}
      </div>

      {/* Embedding Model Configuration */}
      <div className="p-4 border dark:border-gray-700 rounded bg-green-50 dark:bg-green-900/30">
        <h2 className="text-lg font-semibold mb-3 dark:text-white">Embedding 模型</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">用于 AI 分析的语义搜索功能，需要 OpenAI 兼容的 Embedding API</p>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">AI 渠道</label>
            <select
              value={embeddingConfig.provider_id || ''}
              onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, provider_id: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            >
              <option value="">请选择渠道</option>
              {providers.map(provider => (
                <option key={provider.id} value={provider.id}>{provider.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">模型名称</label>
            <input
              type="text"
              value={embeddingConfig.model}
              onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, model: e.target.value })}
              placeholder="text-embedding-3-small"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              常用模型：text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002
            </p>
          </div>
          <label className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={embeddingConfig.auto_generate}
              onChange={(e) => setEmbeddingConfig({ ...embeddingConfig, auto_generate: e.target.checked })}
              className="mt-1"
            />
            <span>
              新文章入库后自动生成 Embedding
              <span className="block text-xs text-gray-400 dark:text-gray-500">
                关闭后不会随订阅刷新自动生成，手动批量索引仍可使用
              </span>
            </span>
          </label>
          <button
            onClick={() => saveEmbeddingConfigMutation.mutate()}
            disabled={saveEmbeddingConfigMutation.isPending || !embeddingConfig.provider_id}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
          >
            保存 Embedding 配置
          </button>
        </div>
      </div>

      {/* Local Translation Configuration */}
      <div className="p-4 border dark:border-gray-700 rounded bg-emerald-50 dark:bg-emerald-900/30">
        <h2 className="text-lg font-semibold mb-3 dark:text-white flex items-center gap-2">
          <Languages className="w-5 h-5" /> 本地翻译
        </h2>
        <div className="space-y-4">
          <div className="flex gap-2 flex-wrap items-center">
            <select
              value={argosSourceLanguage}
              onChange={(e) => setArgosSourceLanguage(e.target.value)}
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
              aria-label="默认源语言"
            >
              {translationSourceLanguages.map((language) => (
                <option key={language.value} value={language.value}>{language.label}</option>
              ))}
            </select>
            <button
              onClick={() => saveArgosConfigMutation.mutate()}
              disabled={saveArgosConfigMutation.isPending}
              className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
            >
              保存默认源语言
            </button>
            <button
              onClick={() => refreshArgosPackagesMutation.mutate()}
              disabled={refreshArgosPackagesMutation.isPending}
              className="flex items-center gap-1 px-3 py-2 border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 rounded hover:bg-emerald-100 dark:hover:bg-emerald-900/50 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${refreshArgosPackagesMutation.isPending ? 'animate-spin' : ''}`} />
              刷新语言包
            </button>
            <button
              onClick={() => {
                setArgosLogPage(1)
                setShowArgosLogsModal(true)
              }}
              className="flex items-center gap-1 px-3 py-2 border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 rounded hover:bg-emerald-100 dark:hover:bg-emerald-900/50"
            >
              <History className="w-4 h-4" />
              翻译记录
            </button>
          </div>

          <div className="flex flex-wrap gap-2 text-xs text-gray-600 dark:text-gray-300">
            <span className="px-2 py-1 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded">
              已安装 {installedArgosPackages.length}
            </span>
            <span className="px-2 py-1 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded">
              可安装 {availableArgosPackages.length}
            </span>
            {argosPackagesLoading && <span className="px-2 py-1 text-emerald-700 dark:text-emerald-300">加载中</span>}
          </div>

          {(argosPackagesErrorText || argosPackages?.available_error) && (
            <div className="p-2 text-sm text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded">
              {argosPackagesErrorText || argosPackages?.available_error}
            </div>
          )}

          <div className="grid gap-3 lg:grid-cols-2">
            <div className="border dark:border-gray-700 rounded bg-white dark:bg-gray-800 overflow-hidden">
              <div className="px-3 py-2 bg-gray-50 dark:bg-gray-700 text-sm font-medium dark:text-white">
                已安装语言包
              </div>
              <div className="divide-y dark:divide-gray-700">
                {installedArgosPackages.length === 0 && (
                  <div className="p-3 text-sm text-gray-500 dark:text-gray-400">暂无已安装语言包</div>
                )}
                {installedArgosPackages.map((pkg) => (
                  <div key={`${pkg.source_language}-${pkg.target_language}`} className="p-3 flex items-center gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium dark:text-white truncate">
                        {getTranslationLanguageLabel(pkg.source_language)} → {getTranslationLanguageLabel(pkg.target_language)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {pkg.source_language} → {pkg.target_language}
                        {pkg.package_version ? ` · v${pkg.package_version}` : ''}
                      </div>
                    </div>
                    <button
                      onClick={() => testArgosPackageMutation.mutate({
                        source_language: pkg.source_language,
                        target_language: pkg.target_language,
                      })}
                      disabled={testArgosPackageMutation.isPending}
                      className="px-2 py-1 text-xs border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 dark:text-gray-200"
                    >
                      测试
                    </button>
                    <button
                      onClick={() => uninstallArgosPackageMutation.mutate(pkg)}
                      disabled={uninstallArgosPackageMutation.isPending}
                      className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded disabled:opacity-50"
                      title="卸载语言包"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="border dark:border-gray-700 rounded bg-white dark:bg-gray-800 p-3 space-y-3">
              <div className="text-sm font-medium dark:text-white">安装语言包</div>
              <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                <select
                  value={argosInstallForm.source_language}
                  onChange={(e) => setArgosInstallForm({ ...argosInstallForm, source_language: e.target.value })}
                  className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  aria-label="安装源语言"
                >
                  {translationSourceLanguages.map((language) => (
                    <option key={language.value} value={language.value}>{language.label}</option>
                  ))}
                </select>
                <select
                  value={argosInstallForm.target_language}
                  onChange={(e) => setArgosInstallForm({ ...argosInstallForm, target_language: e.target.value })}
                  className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  aria-label="安装目标语言"
                >
                  {translationSourceLanguages.map((language) => (
                    <option key={language.value} value={language.value}>{language.label}</option>
                  ))}
                </select>
                <button
                  onClick={() => installArgosPackageMutation.mutate(argosInstallForm)}
                  disabled={
                    installArgosPackageMutation.isPending ||
                    argosInstallForm.source_language === argosInstallForm.target_language ||
                    selectedInstallPackageInstalled
                  }
                  className="flex items-center justify-center gap-1 px-3 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
                >
                  <Download className="w-4 h-4" /> 安装
                </button>
              </div>
              {selectedInstallPackageInstalled && (
                <div className="text-xs text-emerald-700 dark:text-emerald-300">当前语言包已安装</div>
              )}

              <div className="space-y-2">
                <div className="text-sm font-medium dark:text-white">可安装语言包</div>
                {visibleAvailableArgosPackages.length === 0 ? (
                  <div className="text-sm text-gray-500 dark:text-gray-400">暂无可安装列表</div>
                ) : (
                  <div className="grid gap-2">
                    {visibleAvailableArgosPackages.map((pkg) => (
                      <div key={`${pkg.source_language}-${pkg.target_language}`} className="flex items-center gap-2 text-sm">
                        <span className="flex-1 min-w-0 truncate dark:text-gray-200">
                          {getTranslationLanguageLabel(pkg.source_language)} → {getTranslationLanguageLabel(pkg.target_language)}
                        </span>
                        <button
                          onClick={() => installArgosPackageMutation.mutate({
                            source_language: pkg.source_language,
                            target_language: pkg.target_language,
                          })}
                          disabled={installArgosPackageMutation.isPending}
                          className="px-2 py-1 text-xs border border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 rounded hover:bg-emerald-50 dark:hover:bg-emerald-900/30 disabled:opacity-50"
                        >
                          安装
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="border dark:border-gray-700 rounded bg-white dark:bg-gray-800 p-3 space-y-3">
            <div className="text-sm font-medium dark:text-white">翻译测试</div>
            <div className="grid gap-2 md:grid-cols-[150px_150px_1fr_auto]">
              <select
                value={argosTestForm.source_language}
                onChange={(e) => setArgosTestForm({ ...argosTestForm, source_language: e.target.value })}
                className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                aria-label="测试源语言"
              >
                {translationSourceLanguages.map((language) => (
                  <option key={language.value} value={language.value}>{language.label}</option>
                ))}
              </select>
              <select
                value={argosTestForm.target_language}
                onChange={(e) => setArgosTestForm({ ...argosTestForm, target_language: e.target.value })}
                className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                aria-label="测试目标语言"
              >
                {translationSourceLanguages.map((language) => (
                  <option key={language.value} value={language.value}>{language.label}</option>
                ))}
              </select>
              <input
                type="text"
                value={argosTestForm.text}
                onChange={(e) => setArgosTestForm({ ...argosTestForm, text: e.target.value })}
                className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                placeholder="测试文本"
              />
              <button
                onClick={() => testArgosPackageMutation.mutate(argosTestForm)}
                disabled={
                  testArgosPackageMutation.isPending ||
                  !argosTestForm.text.trim() ||
                  argosTestForm.source_language === argosTestForm.target_language
                }
                className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
              >
                测试
              </button>
            </div>
            {argosTestResult && (
              <div className={`p-2 text-sm border rounded ${
                argosTestResult.success
                  ? 'text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-900/30 border-emerald-200 dark:border-emerald-800'
                  : 'text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800'
              }`}>
                <div>{argosTestResult.message}</div>
                {argosTestResult.translation && (
                  <div className="mt-1 text-gray-700 dark:text-gray-200 break-words">{argosTestResult.translation}</div>
                )}
              </div>
            )}
          </div>

          {showArgosLogsModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
              <div className="w-full max-w-6xl max-h-[85vh] bg-white dark:bg-gray-900 border dark:border-gray-700 rounded shadow-xl flex flex-col overflow-hidden">
                <div className="px-4 py-3 border-b dark:border-gray-700 flex flex-wrap items-center gap-2">
                  <div className="text-base font-medium dark:text-white">本地翻译记录</div>
                  <span className="text-xs text-gray-500 dark:text-gray-400">共 {argosLogTotal} 条</span>
                  <button
                    onClick={() => queryClient.invalidateQueries({ queryKey: ['argos-translation-logs'] })}
                    className="ml-auto p-1.5 text-gray-500 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
                    title="刷新记录"
                  >
                    <RefreshCw className={`w-4 h-4 ${argosLogsLoading ? 'animate-spin' : ''}`} />
                  </button>
                  <button
                    onClick={() => {
                      if (window.confirm('确定清除所有本地翻译记录？')) {
                        clearArgosLogsMutation.mutate()
                      }
                    }}
                    disabled={clearArgosLogsMutation.isPending || argosLogTotal === 0}
                    className="flex items-center gap-1 px-2 py-1.5 text-sm text-red-600 dark:text-red-300 border border-red-200 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-900/30 disabled:opacity-50"
                  >
                    <Trash2 className="w-4 h-4" />
                    清除
                  </button>
                  <button
                    onClick={() => setShowArgosLogsModal(false)}
                    className="p-1.5 text-gray-500 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
                    title="关闭"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 overflow-auto">
                  <table className="w-full min-w-[920px] text-sm">
                    <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
                      <tr>
                        <th className="p-3 text-left">文章</th>
                        <th className="p-3 text-left">订阅源</th>
                        <th className="p-3 text-left">语言</th>
                        <th className="p-3 text-left">字符</th>
                        <th className="p-3 text-left">耗时</th>
                        <th className="p-3 text-left">状态</th>
                        <th className="p-3 text-left">时间</th>
                        <th className="p-3 text-left">错误</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y dark:divide-gray-700">
                      {argosLogs.map((log) => (
                        <tr key={log.id} className="dark:text-gray-100">
                          <td className="p-3 max-w-[240px] truncate" title={log.article_title || ''}>
                            {log.article_title || '-'}
                          </td>
                          <td className="p-3 max-w-[160px] truncate text-gray-600 dark:text-gray-300" title={log.feed_title || ''}>
                            {log.feed_title || '-'}
                          </td>
                          <td className="p-3 text-gray-600 dark:text-gray-300">
                            {log.source_language} → {log.target_language}
                          </td>
                          <td className="p-3 text-gray-600 dark:text-gray-300">
                            {(log.title_chars + log.content_chars).toLocaleString()}
                            <span className="text-xs text-gray-400 dark:text-gray-500 ml-1">
                              ({log.title_chars}/{log.content_chars})
                            </span>
                          </td>
                          <td className="p-3 font-mono text-gray-700 dark:text-gray-200">
                            {formatDurationMs(log.duration_ms)}
                          </td>
                          <td className={`p-3 ${getArgosLogStatusClass(log.status)}`}>
                            {getArgosLogStatusLabel(log.status)}
                          </td>
                          <td className="p-3 text-gray-500 dark:text-gray-400">
                            <div>{formatDateTime(log.started_at)}</div>
                            {log.completed_at && (
                              <div className="text-xs">{formatDateTime(log.completed_at)}</div>
                            )}
                          </td>
                          <td className="p-3 max-w-[220px] truncate text-gray-500 dark:text-gray-400" title={log.error || ''}>
                            {log.error || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!argosLogsLoading && argosLogs.length === 0 && (
                    <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无本地翻译记录</div>
                  )}
                  {argosLogsLoading && argosLogs.length === 0 && (
                    <div className="p-4 text-center text-gray-500 dark:text-gray-400">加载中...</div>
                  )}
                </div>
                {argosLogTotalPages > 1 && (
                  <div className="px-4 py-3 border-t dark:border-gray-700 flex items-center justify-end gap-2 text-sm">
                    <button
                      onClick={() => setArgosLogPage((page) => Math.max(1, page - 1))}
                      disabled={argosLogPage <= 1}
                      className="px-2 py-1 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 dark:text-gray-200"
                    >
                      上一页
                    </button>
                    <span className="text-gray-500 dark:text-gray-400">
                      {argosLogPage} / {argosLogTotalPages}
                    </span>
                    <button
                      onClick={() => setArgosLogPage((page) => Math.min(argosLogTotalPages, page + 1))}
                      disabled={argosLogPage >= argosLogTotalPages}
                      className="px-2 py-1 border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 dark:text-gray-200"
                    >
                      下一页
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Mc-Translation Configuration */}
      <div className="p-4 border dark:border-gray-700 rounded bg-cyan-50 dark:bg-cyan-900/30">
        <h2 className="text-lg font-semibold mb-3 dark:text-white flex items-center gap-2">
          <Languages className="w-5 h-5" /> Mc-Translation
        </h2>
        <div className="space-y-3">
          <div className="grid gap-2 md:grid-cols-[1fr_160px_1fr]">
            <input
              type="text"
              value={mcTranslationConfig.base_url}
              onChange={(e) => setMcTranslationConfig({ ...mcTranslationConfig, base_url: e.target.value })}
              placeholder="https://fanyi.aboen.com"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="text"
              value={mcTranslationConfig.model}
              onChange={(e) => setMcTranslationConfig({ ...mcTranslationConfig, model: e.target.value })}
              placeholder="argos"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="password"
              value={mcTranslationConfig.api_key}
              onChange={(e) => setMcTranslationConfig({ ...mcTranslationConfig, api_key: e.target.value })}
              placeholder="API Key"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => saveMcTranslationConfigMutation.mutate()}
              disabled={saveMcTranslationConfigMutation.isPending}
              className="px-4 py-2 bg-cyan-600 text-white rounded hover:bg-cyan-700 disabled:opacity-50"
            >
              保存 Mc-Translation
            </button>
            <button
              onClick={() => testMcTranslationMutation.mutate()}
              disabled={testMcTranslationMutation.isPending || !mcTranslationConfig.api_key.trim()}
              className="px-4 py-2 border border-cyan-300 dark:border-cyan-700 text-cyan-700 dark:text-cyan-300 rounded hover:bg-cyan-100 dark:hover:bg-cyan-900/50 disabled:opacity-50"
            >
              测试连接
            </button>
          </div>
          {mcTranslationTestResult && (
            <div className={`p-2 text-sm border rounded ${
              mcTranslationTestResult.success
                ? 'text-cyan-700 dark:text-cyan-300 bg-cyan-50 dark:bg-cyan-900/30 border-cyan-200 dark:border-cyan-800'
                : 'text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800'
            }`}>
              <div>{mcTranslationTestResult.message}</div>
              {mcTranslationTestResult.translation && (
                <div className="mt-1 text-gray-700 dark:text-gray-200 break-words">{mcTranslationTestResult.translation}</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Google Translate API Keys */}
      <div className="p-4 border dark:border-gray-700 rounded bg-yellow-50 dark:bg-yellow-900/30">
        <h2 className="text-lg font-semibold mb-3 dark:text-white flex items-center gap-2">
          <Languages className="w-5 h-5" /> Google 翻译设置
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
          可配置多个 Google Cloud Translation API Key，并按天数、文章数或字符数达到阈值后自动切换。未配置付费 Key 时仍使用免费接口。
        </p>
        <div className="space-y-3">
          <div className="grid gap-2 md:grid-cols-[1fr_1fr_90px_110px_130px_130px]">
            <input
              type="text"
              value={newGoogleKey.name}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, name: e.target.value })}
              placeholder="名称"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="password"
              value={newGoogleKey.api_key}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, api_key: e.target.value })}
              placeholder="Google Translate API Key"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="number"
              min={1}
              value={newGoogleKey.limit_days}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, limit_days: e.target.value })}
              placeholder="天数"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="number"
              min={1}
              value={newGoogleKey.limit_articles}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, limit_articles: e.target.value })}
              placeholder="文章数"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <input
              type="number"
              min={1}
              value={newGoogleKey.limit_characters}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, limit_characters: e.target.value })}
              placeholder="字符数"
              className="px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <button
              onClick={() => addGoogleKeyMutation.mutate()}
              disabled={!newGoogleKey.name.trim() || !newGoogleKey.api_key.trim() || addGoogleKeyMutation.isPending}
              className="flex items-center justify-center gap-1 px-3 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 disabled:opacity-50"
            >
              <Plus className="w-4 h-4" /> 添加
            </button>
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
            <input
              type="checkbox"
              checked={newGoogleKey.is_active}
              onChange={(e) => setNewGoogleKey({ ...newGoogleKey, is_active: e.target.checked })}
            />
            添加后启用
          </label>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            获取 API Key: <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="text-primary-500 hover:underline">Google Cloud Console</a>。当前共 {googleTranslateKeys.length} 个 Key，启用 {activeGoogleKeyCount} 个。
          </div>

          <div className="overflow-x-auto border dark:border-gray-700 rounded bg-white dark:bg-gray-800">
            <table className="w-full min-w-[960px] text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                <tr>
                  <th className="p-3 text-left">Key</th>
                  <th className="p-3 text-left">切换阈值</th>
                  <th className="p-3 text-left">当前用量</th>
                  <th className="p-3 text-left">状态</th>
                  <th className="p-3 text-left">最近错误</th>
                  <th className="p-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-gray-700">
                {googleTranslateKeys.map((key) => (
                  <tr key={key.id} className="dark:text-gray-100">
                    {editingGoogleKeyId === key.id ? (
                      <>
                        <td className="p-3 space-y-2">
                          <input
                            type="text"
                            value={googleKeyEdit.name}
                            onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, name: e.target.value })}
                            className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                          />
                          <input
                            type="password"
                            value={googleKeyEdit.api_key}
                            onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, api_key: e.target.value })}
                            placeholder="新 Key，留空不变"
                            className="w-full px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                          />
                        </td>
                        <td className="p-3">
                          <div className="grid grid-cols-3 gap-2">
                            <input
                              type="number"
                              min={1}
                              value={googleKeyEdit.limit_days}
                              onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, limit_days: e.target.value })}
                              placeholder="天"
                              className="px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                            />
                            <input
                              type="number"
                              min={1}
                              value={googleKeyEdit.limit_articles}
                              onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, limit_articles: e.target.value })}
                              placeholder="文章"
                              className="px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                            />
                            <input
                              type="number"
                              min={1}
                              value={googleKeyEdit.limit_characters}
                              onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, limit_characters: e.target.value })}
                              placeholder="字符"
                              className="px-2 py-1 border dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-white"
                            />
                          </div>
                        </td>
                        <td className="p-3 text-gray-500 dark:text-gray-400">保存后生效</td>
                        <td className="p-3">
                          <label className="inline-flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={googleKeyEdit.is_active}
                              onChange={(e) => setGoogleKeyEdit({ ...googleKeyEdit, is_active: e.target.checked })}
                            />
                            启用
                          </label>
                        </td>
                        <td className="p-3 text-gray-500 dark:text-gray-400">-</td>
                        <td className="p-3">
                          <div className="flex justify-end gap-1">
                            <button
                              onClick={() => updateGoogleKeyMutation.mutate({ id: key.id, data: googleKeyEdit })}
                              disabled={!googleKeyEdit.name.trim() || updateGoogleKeyMutation.isPending}
                              className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded disabled:opacity-50"
                              title="保存"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => setEditingGoogleKeyId(null)}
                              className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                              title="取消"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="p-3">
                          <div className="font-medium">{key.name}</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">{key.masked_api_key}</div>
                        </td>
                        <td className="p-3 text-gray-600 dark:text-gray-300">
                          <div>天数: {key.limit_days ?? '不限'}</div>
                          <div>文章: {key.limit_articles ?? '不限'}</div>
                          <div>字符: {key.limit_characters ?? '不限'}</div>
                        </td>
                        <td className="p-3 text-gray-600 dark:text-gray-300">
                          <div>{key.usage_article_count} 篇</div>
                          <div>{key.usage_character_count.toLocaleString()} 字符</div>
                          <div className="text-xs text-gray-400 dark:text-gray-500">
                            {key.usage_started_at ? new Date(key.usage_started_at).toLocaleDateString('zh-CN') : '未开始'}
                          </div>
                        </td>
                        <td className="p-3">
                          <div className={key.is_active ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                            {key.is_active ? '启用' : '停用'}
                          </div>
                          {key.is_exhausted && (
                            <div className="text-xs text-yellow-600 dark:text-yellow-400">已达阈值</div>
                          )}
                          <div className="text-xs text-gray-400 dark:text-gray-500">失败 {key.fail_count}/5</div>
                        </td>
                        <td className="p-3 max-w-[220px] truncate text-gray-500 dark:text-gray-400" title={key.last_error || ''}>
                          {key.last_error || '-'}
                        </td>
                        <td className="p-3">
                          <div className="flex justify-end gap-1">
                            <button
                              onClick={() => testGoogleKeyMutation.mutate(key.id)}
                              disabled={testGoogleKeyMutation.isPending}
                              className="p-2 text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded disabled:opacity-50"
                              title="测试"
                            >
                              <RefreshCw className={`w-4 h-4 ${testGoogleKeyMutation.isPending ? 'animate-spin' : ''}`} />
                            </button>
                            <button
                              onClick={() => startGoogleKeyEdit(key)}
                              className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                              title="编辑"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => resetGoogleKeyMutation.mutate(key.id)}
                              disabled={resetGoogleKeyMutation.isPending}
                              className="p-2 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded disabled:opacity-50"
                              title="重置用量"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => updateGoogleKeyMutation.mutate({
                                id: key.id,
                                data: {
                                  name: key.name,
                                  api_key: '',
                                  is_active: !key.is_active,
                                  limit_days: key.limit_days?.toString() || '',
                                  limit_articles: key.limit_articles?.toString() || '',
                                  limit_characters: key.limit_characters?.toString() || '',
                                },
                              })}
                              disabled={updateGoogleKeyMutation.isPending}
                              className="p-2 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-50"
                              title={key.is_active ? '停用' : '启用'}
                            >
                              {key.is_active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}
                            </button>
                            <button
                              onClick={() => deleteGoogleKeyMutation.mutate(key.id)}
                              disabled={deleteGoogleKeyMutation.isPending}
                              className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded disabled:opacity-50"
                              title="删除"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            {googleTranslateKeys.length === 0 && (
              <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无付费 API Key，将使用免费接口</div>
            )}
          </div>
        </div>
      </div>

      {/* Providers */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold dark:text-white">AI 渠道</h2>
          <button
            onClick={openCreateProviderForm}
            className="flex items-center gap-1 px-3 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
          >
            <Plus className="w-4 h-4" /> 添加渠道
          </button>
        </div>

        {showProviderForm && (
          <div className="mb-4 p-4 border dark:border-gray-600 rounded bg-gray-50 dark:bg-gray-700 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="font-medium dark:text-white">{isEditingProvider ? '编辑渠道' : '添加渠道'}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {isEditingProvider
                    ? '可在这里修改渠道配置，并手动获取所有模型。'
                    : '先保存渠道，再在这里手动获取所有模型。'}
                </p>
              </div>
              {editingProvider && (
                <span className="text-xs px-2 py-1 rounded bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-300 border dark:border-gray-600">
                  当前模型 {editingProviderModels.length}
                </span>
              )}
            </div>
            <input
              type="text"
              placeholder="渠道名称"
              value={providerForm.name}
              onChange={(e) => setProviderForm({ ...providerForm, name: e.target.value })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            <select
              value={providerForm.type}
              onChange={(e) => setProviderForm({ ...providerForm, type: e.target.value as AIProviderFormState['type'] })}
              disabled={isEditingProvider}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white disabled:opacity-60"
            >
              <option value="openai">OpenAI</option>
              <option value="gemini">Google Gemini</option>
              <option value="openai_compatible">OpenAI 兼容</option>
            </select>
            <input
              type="password"
              placeholder={isEditingProvider ? '留空则保持当前 API Key 不变' : 'API Key'}
              value={providerForm.api_key}
              onChange={(e) => setProviderForm({ ...providerForm, api_key: e.target.value })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
            />
            {isEditingProvider && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                渠道类型创建后不可修改，API Key 留空时会沿用当前值。
              </p>
            )}
            {providerForm.type === 'openai_compatible' && (
              <>
                <input
                  type="url"
                  placeholder="Base URL (如 https://api.example.com/v1)"
                  value={providerForm.base_url}
                  onChange={(e) => setProviderForm({ ...providerForm, base_url: e.target.value })}
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  OpenAI 兼容渠道按 OpenAI API 规则处理：请填写 API 根路径；若缺少版本前缀，系统会自动补全常见的 `/v1`。不要直接填写 `/chat/completions`、`/models` 等具体接口。部分兼容接口不支持 `/models`，可在保存后手动添加模型 ID。
                </p>
              </>
            )}
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={submitProviderForm}
                disabled={!canSubmitProvider || isSavingProvider}
                className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
              >
                {isSavingProvider ? '保存中...' : isEditingProvider ? '保存修改' : '保存渠道'}
              </button>
              <button
                onClick={() => editingProviderId !== null && testProviderMutation.mutate(editingProviderId)}
                disabled={editingProviderId === null || testProviderMutation.isPending || isSavingProvider}
                className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200 disabled:opacity-50"
              >
                {testProviderMutation.isPending ? '测试中...' : '测试连接'}
              </button>
              <button
                onClick={() => editingProviderId !== null && fetchModelsMutation.mutate(editingProviderId)}
                disabled={editingProviderId === null || fetchModelsMutation.isPending || isSavingProvider}
                className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200 disabled:opacity-50"
              >
                {fetchModelsMutation.isPending ? '获取中...' : '获取所有模型'}
              </button>
              <button
                onClick={closeProviderForm}
                className="px-4 py-2 border dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-600 dark:text-gray-200"
              >
                取消
              </button>
            </div>
            {editingProviderId !== null && (
              <div className="pt-3 border-t dark:border-gray-600 space-y-3">
                <div>
                  <h4 className="text-sm font-medium dark:text-white">手动添加模型</h4>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    适用于 OpenAI 兼容接口不提供模型列表，或你只想直接指定模型 ID 的情况。
                  </p>
                </div>
                <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                  <input
                    type="text"
                    placeholder="模型 ID，例如 gpt-4o-mini"
                    value={providerModelForm.model_id}
                    onChange={(e) => setProviderModelForm({ ...providerModelForm, model_id: e.target.value })}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                  <input
                    type="text"
                    placeholder="显示名称，可留空"
                    value={providerModelForm.name}
                    onChange={(e) => setProviderModelForm({ ...providerModelForm, name: e.target.value })}
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded bg-white dark:bg-gray-800 dark:text-white"
                  />
                  <button
                    onClick={submitProviderModelForm}
                    disabled={!canCreateModel || createModelMutation.isPending}
                    className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
                  >
                    {createModelMutation.isPending ? '添加中...' : '添加模型'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="border dark:border-gray-700 rounded divide-y dark:divide-gray-700">
          {providers.map((provider) => {
            const providerModels = models.filter(m => m.provider_id === provider.id)
            return (
              <div
                key={provider.id}
                className={`p-4 ${editingProviderId === provider.id && showProviderForm ? 'bg-primary-50 dark:bg-primary-900/20' : ''}`}
              >
                <div className="flex items-center gap-4 mb-2">
                  <div className="flex-1">
                    <h3 className="font-medium dark:text-white">{provider.name}</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{provider.type}</p>
                  </div>
                  <button
                    onClick={() => openEditProviderForm(provider)}
                    className="flex items-center gap-1 px-3 py-1 text-sm border dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200"
                  >
                    <Edit2 className="w-4 h-4" />
                    编辑
                  </button>
                  <button
                    onClick={() => deleteProviderMutation.mutate(provider.id)}
                    disabled={deleteProviderMutation.isPending}
                    className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded disabled:opacity-50"
                    title="删除渠道"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {providerModels.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {providerModels.map(model => (
                      <span
                        key={model.id}
                        className={`px-2 py-0.5 text-xs rounded ${model.is_default ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-400' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'}`}
                      >
                        {model.model_id}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
          {providers.length === 0 && (
            <div className="p-4 text-center text-gray-500 dark:text-gray-400">暂无 AI 渠道</div>
          )}
        </div>
      </div>

      {/* Prompts */}
      <div>
        <h2 className="text-lg font-semibold mb-4 dark:text-white">Prompt 设置</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              翻译 Prompt
              <span className="text-gray-400 font-normal ml-2">（使用 {'{target_language}'} 作为目标语言占位符）</span>
            </label>
            <textarea
              value={prompts.translate}
              onChange={(e) => setPrompts({ ...prompts, translate: e.target.value })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded h-24 text-sm bg-white dark:bg-gray-700 dark:text-white"
              placeholder="You are a translator..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              整理 Prompt
            </label>
            <textarea
              value={prompts.summarize}
              onChange={(e) => setPrompts({ ...prompts, summarize: e.target.value })}
              className="w-full px-3 py-2 border dark:border-gray-600 rounded h-24 text-sm bg-white dark:bg-gray-700 dark:text-white"
              placeholder="You are a summarizer..."
            />
          </div>
          <label className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={autoGenerateSummaries}
              onChange={(e) => setAutoGenerateSummaries(e.target.checked)}
              className="mt-1"
            />
            <span>
              新文章入库后自动生成 AI 摘要
              <span className="block text-xs text-gray-400 dark:text-gray-500">
                关闭后不会随订阅刷新自动生成，单个订阅源的 AI 整理开关仍会保留
              </span>
            </span>
          </label>
          <button
            onClick={() => savePromptsMutation.mutate()}
            disabled={savePromptsMutation.isPending}
            className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
          >
            保存 Prompt
          </button>
        </div>
      </div>
    </div>
  )
}
