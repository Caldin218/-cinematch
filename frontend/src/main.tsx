import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HealthPage } from './pages/HealthPage'
import { Discover } from './Discover'
import { AuthLayout, UserLayout } from './components'
import './styles.css'
const queryClient = new QueryClient({defaultOptions:{queries:{staleTime:30000,retry:1,refetchOnWindowFocus:false}}})
createRoot(document.getElementById('root')!).render(<StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><Routes><Route element={<UserLayout/>}><Route path="/" element={<Discover/>}/></Route><Route path="/login" element={<AuthLayout/>}/><Route path="/register" element={<AuthLayout/>}/><Route path="/health" element={<HealthPage/>}/><Route path="*" element={<main className="state"><h1>Không tìm thấy trang</h1><a href="/">Về trang chủ</a></main>}/></Routes></BrowserRouter></QueryClientProvider></StrictMode>)
