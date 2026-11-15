import { api } from "./api";
export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}
export interface Genre {
  id: number;
  name: string;
}
export interface Movie {
  id: number;
  title: string;
  original_title: string | null;
  synopsis: string | null;
  release_year: number | null;
  runtime_minutes: number | null;
  poster_url: string | null;
  trailer_youtube_id: string | null;
  genres: Genre[];
  average_rating: number | null;
  rating_count: number;
  popularity: number;
  comment_count: number;
}
export interface Recommendation {
  movie_id: number;
  rank: number;
  method: string;
  ranking_score: number | null;
  predicted_rating: number | null;
  popularity_score: number | null;
}
export interface Recommendations {
  items: Recommendation[];
  generated_at: string | null;
  algorithm_version: string;
  status: "ready" | "stale" | "unavailable";
  fallback: string | null;
}
export interface Interaction {
  rating: number | null;
  favorite: boolean;
  watchlist: boolean;
  watched: boolean;
}
export interface Comment {
  id: number;
  movie_id: number;
  username: string;
  body: string;
  created_at: string;
  likes: number;
  liked: boolean;
}
export const portal = {
  get: async <T>(
    path: string,
    params?: object,
    signal?: AbortSignal,
  ): Promise<T> =>
    (await api.get<{ data: T }>(`/v1${path}`, { params, signal })).data.data,
  post: async <T>(path: string, body?: object): Promise<T> =>
    (await api.post<{ data: T }>(`/v1${path}`, body)).data?.data,
};
export function errorMessage(error: unknown) {
  return (
    error as { response?: { status?: number; data?: { message?: string } } }
  )?.response?.status === 401
    ? "Vui lòng đăng nhập để tiếp tục."
    : (error as { response?: { data?: { message?: string } } })?.response?.data
        ?.message || "Không thể kết nối. Vui lòng thử lại.";
}
