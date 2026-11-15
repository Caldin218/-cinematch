import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clapperboard, Search } from "lucide-react";
import {
  MovieRowCard,
  RecommendationRefreshButton,
  EmptyState,
  LoadingSkeleton,
  ErrorState,
  useToast,
} from "./components";
import {
  portal,
  errorMessage,
  type Movie,
  type Genre,
  type Page,
  type Recommendations,
} from "./lib/portal";
import { useAuth } from "./store/auth";
export function Discover() {
  const token = useAuth((s) => s.accessToken),
    qc = useQueryClient(),
    toast = useToast();
  const [search, setSearch] = useState(""),
    [q, setQ] = useState(""),
    [genre, setGenre] = useState(""),
    [year, setYear] = useState(""),
    [rating, setRating] = useState(""),
    [sort, setSort] = useState("match"),
    [page, setPage] = useState(1),
    [size, setSize] = useState(10),
    [refreshFrom, setRefreshFrom] = useState<string | null | undefined>(
      undefined,
    );
  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(search.trim());
      setPage(1);
    }, 200);
    return () => clearTimeout(timer);
  }, [search]);
  const genres = useQuery({
    queryKey: ["genres"],
    queryFn: ({ signal }) => portal.get<Genre[]>("/genres", undefined, signal),
  });
  const recs = useQuery({
    queryKey: ["recommendations", token],
    queryFn: ({ signal }) =>
      portal.get<Recommendations>("/recommendations/me", { n: 100 }, signal),
    enabled: !!token,
    refetchInterval: refreshFrom !== undefined ? 2500 : false,
  });
  useEffect(() => {
    if (
      refreshFrom !== undefined &&
      recs.data?.status === "ready" &&
      recs.data.generated_at &&
      recs.data.generated_at !== refreshFrom
    ) {
      setRefreshFrom(undefined);
      toast("Ma trận gợi ý đã được tính toán lại.");
      void qc.invalidateQueries({ queryKey: ["discovery"] });
    }
  }, [recs.data, refreshFrom, qc, toast]);
  useEffect(() => {
    if (refreshFrom === undefined) return;
    const timer = setTimeout(() => {
      setRefreshFrom(undefined);
      toast("Gợi ý vẫn đang xử lý. Bạn có thể kiểm tra lại sau.");
    }, 120000);
    return () => clearTimeout(timer);
  }, [refreshFrom, toast]);
  const personalized =
    sort === "match" &&
    !!token &&
    !q &&
    !genre &&
    !year &&
    !rating &&
    !recs.isError &&
    !!recs.data?.items.length;
  const movies = useQuery({
    queryKey: [
      "discovery",
      q,
      genre,
      year,
      rating,
      sort,
      page,
      size,
      personalized,
      recs.data?.generated_at,
      token,
    ],
    queryFn: async ({ signal }) => {
      if (personalized) {
        const ranked = recs.data!.items;
        const items = await Promise.all(
          ranked
            .slice((page - 1) * size, page * size)
            .map((r) =>
              portal.get<Movie>(`/movies/${r.movie_id}`, undefined, signal),
            ),
        );
        return { items, page, page_size: size, total: ranked.length };
      }
      return portal.get<Page<Movie>>(
        "/movies",
        {
          q: q || undefined,
          genre_id: genre || undefined,
          release_year: year || undefined,
          min_rating: rating || undefined,
          sort,
          page,
          page_size: size,
        },
        signal,
      );
    },
  });
  const refresh = useMutation({
    mutationFn: () => portal.post("/recommendations/refresh"),
    onSuccess: () => {
      setRefreshFrom(recs.data?.generated_at ?? null);
      toast("Đã lên lịch tính lại gợi ý…");
      void qc.invalidateQueries({ queryKey: ["recommendations"] });
    },
    onError: (e) => toast(errorMessage(e)),
  });
  function filter(set: (v: string) => void, v: string) {
    set(v);
    setPage(1);
  }
  return (
    <>
      <header>
        <Link className="brand" to="/discover">
          <span className="logo">
            <Clapperboard />
          </span>
          <span>
            CineMatch<small>MOVIE DISCOVERY HUB</small>
          </span>
        </Link>
        <div className="search">
          <Search size={18} />
          <input
            maxLength={255}
            aria-label="Tìm kiếm phim"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm tựa phim, tựa gốc, nội dung…"
          />
        </div>
        <RecommendationRefreshButton
          loading={
            refresh.isPending ||
            refreshFrom !== undefined ||
            (!!token && recs.isPending)
          }
          onClick={() =>
            token
              ? refresh.mutate()
              : toast("Đăng nhập để nhận gợi ý cá nhân hóa.")
          }
        />
        {token ? (
          <button
            onClick={() => {
              useAuth.getState().setToken(null);
              qc.clear();
            }}
          >
            Đăng xuất
          </button>
        ) : (
          <Link className="avatar" to="/login">
            Đăng nhập
          </Link>
        )}
      </header>
      <main className="discover">
        <section className="hero">
          <div>
            <p className="eyebrow">YOUR NEXT GREAT STORY</p>
            <h1>
              Khám Phá Phim Dành Riêng Cho Bạn <span>AI Recommendations</span>
            </h1>
            <p>
              Điện ảnh kết nối cảm xúc. Tìm câu chuyện tiếp theo dành cho bạn.
            </p>
          </div>
          <div className="algorithm">✦ Cá nhân hóa trải nghiệm</div>
        </section>
        <div className="filters">
          <label>
            Thể loại
            <select
              aria-label="Thể loại"
              value={genre}
              onChange={(e) => filter(setGenre, e.target.value)}
            >
              <option value="">Tất cả thể loại</option>
              {genres.data?.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Năm phát hành
            <input
              aria-label="Năm phát hành"
              type="number"
              min="1888"
              max="9999"
              placeholder="Tất cả"
              value={year}
              onChange={(e) => filter(setYear, e.target.value)}
            />
          </label>
          <label>
            Điểm tối thiểu
            <select
              aria-label="Điểm tối thiểu"
              value={rating}
              onChange={(e) => filter(setRating, e.target.value)}
            >
              <option value="">Tất cả</option>
              {[1, 2, 3, 4, 4.5, 5].map((n) => (
                <option key={n} value={n}>
                  {n} / 5 ★
                </option>
              ))}
            </select>
          </label>
          <label>
            Sắp xếp
            <select
              aria-label="Sắp xếp"
              value={sort}
              onChange={(e) => filter(setSort, e.target.value)}
            >
              <option value="match">Match Score</option>
              <option value="popularity">Popularity</option>
              <option value="rating">Rating</option>
              <option value="release_year">Release Year</option>
            </select>
          </label>
        </div>
        {genres.isError && (
          <p role="alert">
            Không tải được thể loại.{" "}
            <button onClick={() => genres.refetch()}>Thử lại</button>
          </p>
        )}
        <div className="section-label">
          <span>
            {personalized ? "ĐƯỢC CHỌN CHO BẠN" : "KHÁM PHÁ ĐIỆN ẢNH"}
          </span>
          <span>{movies.data?.total ?? "…"} bộ phim</span>
        </div>
        {sort === "match" && !personalized && (
          <p className="muted">
            {token
              ? "Gợi ý cá nhân chưa có sẵn. Khám phá phim phổ biến trong lúc chờ."
              : "Đăng nhập để nhận Match Score cá nhân. Đang hiển thị phim phổ biến."}
          </p>
        )}
        {movies.isPending ? (
          <LoadingSkeleton />
        ) : movies.isError ? (
          <ErrorState retry={() => movies.refetch()} />
        ) : movies.data.items.length ? (
          movies.data.items.map((m) => (
            <MovieRowCard
              key={m.id}
              movie={m}
              recommendation={recs.data?.items.find((r) => r.movie_id === m.id)}
              metadata={recs.data}
            />
          ))
        ) : (
          <EmptyState />
        )}
        <nav className="pagination" aria-label="Phân trang">
          <button
            disabled={page === 1 || movies.isFetching}
            onClick={() => setPage((p) => p - 1)}
          >
            ← Trước
          </button>
          <span>
            Trang {page} /{" "}
            {Math.max(1, Math.ceil((movies.data?.total ?? 0) / size))}
          </span>
          <button
            disabled={
              movies.isFetching || page * size >= (movies.data?.total ?? 0)
            }
            onClick={() => setPage((p) => p + 1)}
          >
            Sau →
          </button>
          <label>
            Phim / trang{" "}
            <select
              aria-label="Phim mỗi trang"
              value={size}
              onChange={(e) => {
                setSize(Number(e.target.value));
                setPage(1);
              }}
            >
              {[5, 10, 20, 50].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
        </nav>
      </main>
    </>
  );
}
