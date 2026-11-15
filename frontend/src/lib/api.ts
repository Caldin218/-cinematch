import axios from 'axios'

export const api = axios.create({ baseURL: '/api', timeout: 10000 })

export interface Health {
  status: 'ok' | 'ready' | 'not_ready'
  checks: Record<string, 'up' | 'down'>
}

export async function getReadiness(): Promise<Health> {
  // A 503 response is valid diagnostic data; transport errors still reject.
  const { data } = await api.get<Health>('/health/ready', {
    validateStatus: (status) => status === 200 || status === 503,
  })
  return data
}
import { useAuth } from '../store/auth'
api.interceptors.request.use((config) => { const token = useAuth.getState().accessToken; if (token) config.headers.Authorization = `Bearer ${token}`; return config })
api.interceptors.response.use(response => response, (error: unknown) => { if (axios.isAxiosError(error) && error.response?.status === 401) useAuth.getState().setToken(null); return Promise.reject(error) })
