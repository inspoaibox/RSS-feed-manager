import { useThemeStore,type ThemeColor } from '@/stores/themeStore'

export default function AppearanceTab() {
  const { mode, color, setMode, setColor } = useThemeStore()

  // 主题颜色
  const colorOptions: { value: ThemeColor; label: string; bgClass: string }[] = [
    { value: 'blue', label: '蓝色', bgClass: 'bg-blue-500' },
    { value: 'green', label: '绿色', bgClass: 'bg-green-500' },
    { value: 'purple', label: '紫色', bgClass: 'bg-purple-500' },
    { value: 'orange', label: '橙色', bgClass: 'bg-orange-500' },
    { value: 'rose', label: '玫红', bgClass: 'bg-rose-500' },
    { value: 'cyan', label: '青色', bgClass: 'bg-cyan-500' },
    { value: 'indigo', label: '靛蓝', bgClass: 'bg-indigo-500' },
    { value: 'amber', label: '琥珀', bgClass: 'bg-amber-500' },
    { value: 'red', label: '红色', bgClass: 'bg-red-500' },
    { value: 'pink', label: '粉色', bgClass: 'bg-pink-500' },
    { value: 'teal', label: '青绿', bgClass: 'bg-teal-500' },
    { value: 'slate', label: '石板', bgClass: 'bg-slate-500' },
  ]

  return (
    <div className="space-y-8">
      {/* 主题模式 */}
      <div>
        <h3 className="font-medium mb-4 dark:text-white">主题模式</h3>
        <div className="flex gap-4">
          <button
            onClick={() => setMode('light')}
            className={`flex-1 p-4 rounded-xl border-2 transition-all duration-300 ${
              mode === 'light'
                ? 'border-primary-500 bg-gradient-to-br from-primary-50 to-white dark:from-primary-900/30 dark:to-gray-800 shadow-lg'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'
            }`}
          >
            <div className="w-full h-24 rounded-lg bg-gradient-to-br from-white to-gray-50 border mb-3 flex items-center justify-center overflow-hidden relative">
              <div className="absolute top-2 left-2 w-3 h-3 rounded-full bg-yellow-400 shadow-lg shadow-yellow-400/50"></div>
              <div className="w-16 h-3 bg-gray-200 rounded-full"></div>
            </div>
            <p className={`text-center font-medium ${mode === 'light' ? 'text-primary-600' : 'text-gray-600 dark:text-gray-400'}`}>
              浅色模式
            </p>
          </button>
          <button
            onClick={() => setMode('dark')}
            className={`flex-1 p-4 rounded-xl border-2 transition-all duration-300 ${
              mode === 'dark'
                ? 'border-primary-500 bg-gradient-to-br from-primary-50 to-white dark:from-primary-900/30 dark:to-gray-800 shadow-lg'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'
            }`}
          >
            <div className="w-full h-24 rounded-lg bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 mb-3 flex items-center justify-center overflow-hidden relative">
              <div className="absolute top-2 left-2 w-3 h-3 rounded-full bg-indigo-400 shadow-lg shadow-indigo-400/50"></div>
              <div className="absolute top-3 right-3 w-1.5 h-1.5 rounded-full bg-white/30"></div>
              <div className="absolute top-5 right-6 w-1 h-1 rounded-full bg-white/20"></div>
              <div className="w-16 h-3 bg-gray-600 rounded-full"></div>
            </div>
            <p className={`text-center font-medium ${mode === 'dark' ? 'text-primary-600 dark:text-primary-400' : 'text-gray-600 dark:text-gray-400'}`}>
              深色模式
            </p>
          </button>
        </div>
      </div>

      {/* 主题颜色 */}
      <div>
        <h3 className="font-medium mb-4 dark:text-white">主题颜色</h3>
        <div className="flex gap-4 flex-wrap">
          {colorOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setColor(opt.value)}
              className={`flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all ${
                color === opt.value
                  ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              <div className={`w-10 h-10 rounded-full ${opt.bgClass}`}></div>
              <span className={`text-sm ${color === opt.value ? 'text-primary-600 dark:text-primary-400 font-medium' : 'text-gray-600 dark:text-gray-400'}`}>
                {opt.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* 预览 */}
      <div>
        <h3 className="font-medium mb-4 dark:text-white">预览</h3>
        <div className={`p-4 rounded-lg border ${mode === 'dark' ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-primary-500"></div>
            <div>
              <p className={`font-medium ${mode === 'dark' ? 'text-white' : 'text-gray-900'}`}>示例标题</p>
              <p className={`text-sm ${mode === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>这是一段示例文字</p>
            </div>
          </div>
          <button className="px-4 py-2 rounded text-white bg-primary-600 hover:bg-primary-700">
            示例按钮
          </button>
        </div>
      </div>
    </div>
  )
}
