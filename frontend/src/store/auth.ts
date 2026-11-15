import { create } from "zustand";
interface AuthState {
  accessToken: string | null;
  setToken: (token: string | null) => void;
}
// Keep credentials in memory; signing out also clears all private Query caches.
export const useAuth = create<AuthState>((set) => ({
  accessToken: null,
  setToken: (accessToken) => set({ accessToken }),
}));
