/**
 * Desktop version App component - No authentication
 * Replace frontend/src/App.tsx with this file for desktop build
 */
import { Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '@/components/ThemeProvider'
import MainLayout from '@/components/layout/MainLayout'
import HomePage from '@/pages/HomePage'
import SettingsPage from '@/pages/SettingsPage'
import StatsPage from '@/pages/StatsPage'
import AIAnalysisPage from '@/pages/AIAnalysisPage'
import RecommendationsPage from '@/pages/RecommendationsPage'

function App() {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<HomePage />} />
            <Route path="ai-analysis" element={<AIAnalysisPage />} />
            <Route path="recommendations" element={<RecommendationsPage />} />
            <Route path="stats" element={<StatsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </div>
    </ThemeProvider>
  )
}

export default App
