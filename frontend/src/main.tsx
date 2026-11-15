import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HealthPage } from './pages/HealthPage'
import './styles.css'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode><QueryClientProvider client={queryClient}><BrowserRouter>
    <Routes><Route path="/" element={<Navigate to="/health" replace />} />
      <Route path="/health" element={<HealthPage />} />
      <Route path="*" element={<main className="p-10"><h1>Page not found</h1><a href="/health">System health</a></main>} />
    </Routes>
  </BrowserRouter></QueryClientProvider></StrictMode>,
)
