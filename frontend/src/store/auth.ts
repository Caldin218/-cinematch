import { create } from 'zustand'
interface AuthState { accessToken: string | null; setToken: (token: string | null) => void }
export const useAuth = create<AuthState>((set) => ({ accessToken: null, setToken: (accessToken) => set({ accessToken }) }))
