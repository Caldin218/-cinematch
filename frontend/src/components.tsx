import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Link,
  Outlet,
  useLocation,
  useNavigate,
  useParams,
} from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bookmark,
  ChevronDown,
  Clapperboard,
  Eye,
  EyeOff,
  Heart,
  MessageCircle,
  Sparkles,
  LoaderCircle,
  Check,
} from "lucide-react";
import { api } from "./lib/api";
import {
  portal,
  errorMessage,
  type Movie,
  type Recommendation,
  type Recommendations,
  type Interaction,
  type Comment,
  type Page,
} from "./lib/portal";
import { useAuth } from "./store/auth";
const ToastContext = createContext<(message: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState(""),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const notify = useCallback((value: string) => {
    setMessage(value);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(""), 6000);
  }, []);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  return (
    <ToastContext.Provider value={notify}>
      {children}
      {message && (
        <div className="toast" role="status" aria-label="Thông báo">
          {message}
          <button aria-label="Đóng thông báo" onClick={() => setMessage("")}>
            ×
          </button>
        </div>
      )}
    </ToastContext.Provider>
  );
}
export function PosterStarRating({
  value,
  onChange,
  disabled = false,
}: {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  return (
    <div className="star-bar" onMouseLeave={() => setHover(null)}>
      <div className="stars" role="group" aria-label="Đánh giá phim">
        {Array.from({ length: 10 }, (_, i) => (
          <button
            disabled={disabled}
            key={i}
            aria-label={`Rate ${(i + 1) / 2} stars`}
            aria-pressed={value === (i + 1) / 2}
            onFocus={() => setHover((i + 1) / 2)}
            onBlur={() => setHover(null)}
            onMouseEnter={() => setHover((i + 1) / 2)}
            onClick={() => onChange((i + 1) / 2)}
            className={(hover ?? value) >= (i + 1) / 2 ? "lit" : ""}
          >
            ★
          </button>
        ))}
      </div>
      <b>{(hover ?? value).toFixed(1)} ★</b>
    </div>
  );
}
export function RecommendationRefreshButton({
  loading = false,
  onClick,
}: {
  loading?: boolean;
  onClick: () => void;
}) {
  return (
    <button className="refresh" disabled={loading} onClick={onClick}>
      {loading ? (
        <LoaderCircle className="spin" size={17} />
      ) : (
        <Sparkles size={17} />
      )}{" "}
      {loading ? "Đang tính toán…" : "Gợi ý mới"}
    </button>
  );
}
export function CommentThread({ movieId }: { movieId: number }) {
  const token = useAuth((s) => s.accessToken),
    toast = useToast(),
    qc = useQueryClient(),
    [text, setText] = useState(""),
    [page, setPage] = useState(1),
    input = useRef<HTMLInputElement>(null),
    key = ["comments", movieId, page, token];
  const comments = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      portal.get<Page<Comment>>(
        `/movies/${movieId}/comments`,
        { page, page_size: 20 },
        signal,
      ),
    refetchInterval: 10000,
  });
  const submit = useMutation({
    mutationFn: () =>
      portal.post(`/movies/${movieId}/comments`, { body: text.trim() }),
    onSuccess: () => {
      setText("");
      setPage(1);
      void qc.invalidateQueries({ queryKey: ["comments", movieId] });
      void qc.invalidateQueries({ queryKey: ["discovery"] });
      void qc.invalidateQueries({ queryKey: ["movie", movieId] });
    },
    onError: (e) => toast(errorMessage(e)),
  });
  const like = useMutation({
    mutationFn: async (c: Comment) => {
      if (c.liked) await api.delete(`/v1/comments/${c.id}/like`);
      else await portal.post(`/comments/${c.id}/like`);
    },
    onMutate: async (c) => {
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueryData<Page<Comment>>(key);
      qc.setQueryData<Page<Comment>>(
        key,
        (old) =>
          old && {
            ...old,
            items: old.items.map((x) =>
              x.id === c.id
                ? { ...x, liked: !x.liked, likes: x.likes + (x.liked ? -1 : 1) }
                : x,
            ),
          },
      );
      return { previous };
    },
    onError: (e, _c, context) => {
      if (context?.previous) qc.setQueryData(key, context.previous);
      toast(errorMessage(e));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });
  return (
    <section className="discussion">
      <h3>
        <MessageCircle size={18} /> Bình luận cộng đồng{" "}
        <span className="muted">
          {comments.data?.total ?? 0} · cập nhật mỗi 10 giây
        </span>
      </h3>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!token) return toast("Vui lòng đăng nhập để bình luận.");
          if (text.trim()) submit.mutate();
        }}
      >
        <span className="comment-avatar">CM</span>
        <input
          ref={input}
          aria-label="Bình luận"
          maxLength={2000}
          placeholder="Chia sẻ cảm nhận của bạn…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button disabled={!text.trim() || submit.isPending} type="submit">
          {submit.isPending ? "Đang gửi…" : "Gửi bình luận"}
        </button>
      </form>
      {comments.isPending ? (
        <p role="status">Đang tải bình luận…</p>
      ) : comments.isError ? (
        <ErrorState retry={() => comments.refetch()} />
      ) : (
        <>
          <div className="comment-list">
            {!comments.data.items.length && (
              <p className="muted">Hãy bắt đầu cuộc trò chuyện.</p>
            )}
            {comments.data.items.map((c) => (
              <article className="comment" key={c.id}>
                <span className="comment-avatar">
                  {c.username.slice(0, 2).toUpperCase()}
                </span>
                <div>
                  <b>@{c.username}</b>{" "}
                  <time className="muted" dateTime={c.created_at}>
                    {new Date(c.created_at).toLocaleString("vi-VN")}
                  </time>
                  <p>{c.body}</p>
                  <button
                    aria-label={`Thích bình luận của ${c.username}`}
                    className={c.liked ? "saved" : ""}
                    aria-pressed={c.liked}
                    disabled={like.isPending}
                    onClick={() =>
                      token
                        ? like.mutate(c)
                        : toast("Vui lòng đăng nhập để thích bình luận.")
                    }
                  >
                    <Heart size={14} fill={c.liked ? "currentColor" : "none"} />{" "}
                    {c.likes}
                  </button>
                  <button
                    onClick={() => {
                      setText(`@${c.username} `);
                      input.current?.focus();
                    }}
                  >
                    Trả lời
                  </button>
                </div>
              </article>
            ))}
          </div>
          {comments.data.total > 20 && (
            <nav className="pagination">
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Trước
              </button>
              <span>Trang {page}</span>
              <button
                disabled={page * 20 >= comments.data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Sau
              </button>
            </nav>
          )}
        </>
      )}
    </section>
  );
}
function Insights({
  movie,
  recommendation,
  metadata,
}: {
  movie: Movie;
  recommendation?: Recommendation;
  metadata?: Recommendations;
}) {
  const id = movie.trailer_youtube_id,
    safeId = id && /^[\w-]{11}$/.test(id) ? id : null;
  return (
    <div className="insight-grid">
      <section className="insight">
        <h3>
          <Sparkles size={18} /> Vì sao dành cho bạn?
        </h3>
        <p>
          {recommendation
            ? ["user_cf", "hybrid"].includes(recommendation.method)
              ? "Những người có lịch sử đánh giá tương đồng với bạn cũng yêu thích bộ phim này."
              : "Bộ phim nổi bật từ hoạt động cộng đồng, giúp bạn khám phá thêm sở thích mới."
            : "Đánh giá và lưu phim để CineMatch hiểu gu điện ảnh của bạn."}
        </p>
        <dl>
          <dt>Phương pháp</dt>
          <dd>{recommendation?.method ?? "Chưa cá nhân hóa"}</dd>
          <dt>Điểm xếp hạng</dt>
          <dd>
            {recommendation?.ranking_score != null
              ? `${Math.round(recommendation.ranking_score * 100)}%`
              : "Chưa có dữ liệu"}
          </dd>
          <dt>Dự đoán đánh giá</dt>
          <dd>{recommendation?.predicted_rating?.toFixed(1) ?? "—"} / 5</dd>
          <dt>Độ tin cậy</dt>
          <dd>Chưa được API cung cấp</dd>
          <dt>Phiên bản</dt>
          <dd>{metadata?.algorithm_version ?? "—"}</dd>
          <dt>Cập nhật</dt>
          <dd>
            {metadata?.generated_at
              ? new Date(metadata.generated_at).toLocaleString("vi-VN")
              : "—"}
          </dd>
        </dl>
      </section>
      <section className="trailer">
        <h3>Official Trailer</h3>
        {safeId ? (
          <>
            <iframe
              title={`Trailer ${movie.title}`}
              loading="lazy"
              src={`https://www.youtube-nocookie.com/embed/${safeId}`}
              allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              referrerPolicy="strict-origin-when-cross-origin"
            />
            <a
              target="_blank"
              rel="noopener noreferrer"
              href={`https://www.youtube.com/watch?v=${safeId}`}
            >
              Xem trên YouTube ↗
            </a>
          </>
        ) : (
          <div className="trailer-empty">
            <Clapperboard />
            <p>Chưa có trailer chính thức cho phim này.</p>
            <a
              target="_blank"
              rel="noopener noreferrer"
              href={`https://www.youtube.com/results?search_query=${encodeURIComponent(movie.title + " official trailer")}`}
            >
              Tìm trên YouTube ↗
            </a>
          </div>
        )}
      </section>
    </div>
  );
}
export function MovieRowCard({
  movie,
  recommendation,
  metadata,
  expanded = false,
}: {
  movie: Movie;
  recommendation?: Recommendation;
  metadata?: Recommendations;
  expanded?: boolean;
}) {
  const token = useAuth((s) => s.accessToken),
    toast = useToast(),
    qc = useQueryClient(),
    [open, setOpen] = useState(expanded),
    [imageFailed, setImageFailed] = useState(false),
    key = ["interaction", movie.id, token];
  const state = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      portal.get<Interaction>(
        `/interactions/movies/${movie.id}`,
        undefined,
        signal,
      ),
    enabled: !!token,
  });
  const current = state.data ?? {
    rating: null,
    watchlist: false,
    favorite: false,
    watched: false,
  };
  type Change = {
    kind: "rating" | "watchlist" | "favorite" | "watched";
    value: number | boolean;
    existingRating?: boolean;
  };
  const change = useMutation({
    mutationFn: async ({ kind, value, existingRating }: Change) => {
      if (kind === "rating") {
        if (existingRating)
          await api.put(`/v1/interactions/rating/${movie.id}`, { value });
        else
          await portal.post("/interactions/rating", {
            movie_id: movie.id,
            value,
          });
      } else if (kind === "watched")
        await portal.post("/interactions/view", {
          movie_id: movie.id,
          request_id: crypto.randomUUID(),
        });
      else {
        const path = kind === "favorite" ? "favorites" : "watchlist";
        if (value)
          await portal.post(`/interactions/${path}`, { movie_id: movie.id });
        else await api.delete(`/v1/interactions/${path}/${movie.id}`);
      }
    },
    onMutate: async ({ kind, value }) => {
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueryData<Interaction>(key);
      qc.setQueryData(key, { ...current, [kind]: value });
      return { previous };
    },
    onError: (e, _v, context) => {
      qc.setQueryData(
        key,
        context?.previous ?? {
          rating: null,
          watchlist: false,
          favorite: false,
          watched: false,
        },
      );
      toast(errorMessage(e));
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: key });
      void qc.invalidateQueries({ queryKey: ["discovery"] });
      void qc.invalidateQueries({ queryKey: ["movie", movie.id] });
    },
  });
  function act(kind: Change["kind"], value: Change["value"]) {
    if (!token) return toast("Vui lòng đăng nhập để lưu tương tác.");
    if (state.isError)
      return toast("Không tải được trạng thái tương tác. Vui lòng thử lại.");
    change.mutate({ kind, value, existingRating: current.rating != null });
  }
  const disabled = change.isPending || (!!token && state.isPending);
  return (
    <article className="movie">
      <div className="movie-main">
        <div className="poster">
          {movie.poster_url && !imageFailed ? (
            <img
              src={movie.poster_url}
              alt={`Poster ${movie.title}`}
              loading="lazy"
              onError={() => setImageFailed(true)}
            />
          ) : (
            <div className="poster-title">{movie.title}</div>
          )}
          <div className="badges">
            <span>
              ★{" "}
              {movie.average_rating != null
                ? (movie.average_rating * 2).toFixed(1)
                : "—"}
            </span>
            <span>
              {recommendation?.ranking_score != null
                ? `${Math.round(recommendation.ranking_score * 100)}% Khớp gu`
                : "Chưa có Match"}
            </span>
          </div>
          <PosterStarRating
            value={current.rating ?? 0}
            disabled={disabled}
            onChange={(v) => act("rating", v)}
          />
        </div>
        <div className="movie-content">
          <div className="meta">
            <span className="genre">
              {movie.genres.map((g) => g.name).join(" · ") || "Điện ảnh"}
            </span>
            <span>{movie.release_year ?? "—"}</span>
            <span className="stats">
              <Eye size={14} /> {movie.popularity} <MessageCircle size={14} />{" "}
              {movie.comment_count}
            </span>
          </div>
          <h2>
            <Link to={`/movies/${movie.id}`}>{movie.title}</Link>
            {movie.original_title && <small> ({movie.original_title})</small>}
          </h2>
          <div className="overview">
            {movie.synopsis || "Chưa có nội dung giới thiệu."}
          </div>
          <div className="actions">
            <button
              disabled={disabled}
              aria-pressed={current.watchlist}
              className={current.watchlist ? "saved" : ""}
              onClick={() => act("watchlist", !current.watchlist)}
            >
              <Bookmark size={15} />
              {current.watchlist ? "Đã lưu" : "Lưu kho phim"}
            </button>
            <button
              disabled={disabled}
              aria-label="Yêu thích"
              aria-pressed={current.favorite}
              className={current.favorite ? "saved" : ""}
              onClick={() => act("favorite", !current.favorite)}
            >
              <Heart
                size={15}
                fill={current.favorite ? "currentColor" : "none"}
              />
            </button>
            <button
              disabled={disabled || current.watched}
              aria-pressed={current.watched}
              onClick={() => act("watched", true)}
            >
              <Check size={15} />
              {current.watched ? "Đã xem" : "Đánh dấu đã xem"}
            </button>
            <button
              className="expand"
              aria-expanded={open}
              aria-controls={`insights-${movie.id}`}
              onClick={() => setOpen(!open)}
            >
              Insights, Trailer & Bình luận{" "}
              <ChevronDown
                size={16}
                style={{ transform: open ? "rotate(180deg)" : undefined }}
              />
            </button>
          </div>
          {state.isError && (
            <p role="alert">
              Không tải được tương tác.{" "}
              <button onClick={() => state.refetch()}>Thử lại</button>
            </p>
          )}
        </div>
      </div>
      <div
        className={`accordion ${open ? "open" : ""}`}
        id={`insights-${movie.id}`}
        inert={!open}
      >
        <div>
          {open && (
            <>
              <Insights
                movie={movie}
                recommendation={recommendation}
                metadata={metadata}
              />
              <CommentThread movieId={movie.id} />
            </>
          )}
        </div>
      </div>
    </article>
  );
}
export function MovieDetail() {
  const { id } = useParams(),
    movieId = Number(id);
  const token = useAuth((s) => s.accessToken);
  const recommendations = useQuery({
    queryKey: ["recommendations", token],
    queryFn: ({ signal }) =>
      portal.get<Recommendations>("/recommendations/me", { n: 100 }, signal),
    enabled: !!token,
  });
  const movie = useQuery({
    queryKey: ["movie", movieId],
    queryFn: ({ signal }) =>
      portal.get<Movie>(`/movies/${movieId}`, undefined, signal),
    enabled: Number.isSafeInteger(movieId) && movieId > 0,
  });
  return (
    <main className="discover detail">
      <Link to="/discover">← Khám phá phim</Link>
      {!Number.isSafeInteger(movieId) || movieId <= 0 ? (
        <EmptyState />
      ) : movie.isPending ? (
        <LoadingSkeleton />
      ) : movie.isError ? (
        <ErrorState retry={() => movie.refetch()} />
      ) : (
        <>
          <p className="eyebrow">CINEMATCH / MOVIE DETAILS</p>
          <h1>{movie.data.title}</h1>
          <p className="muted">
            {movie.data.runtime_minutes ?? "—"} phút · {movie.data.rating_count}{" "}
            đánh giá
          </p>
          <MovieRowCard
            movie={movie.data}
            expanded
            recommendation={recommendations.data?.items.find(
              (r) => r.movie_id === movieId,
            )}
            metadata={recommendations.data}
          />
        </>
      )}
    </main>
  );
}
export function LoadingSkeleton() {
  return <div className="skeleton" role="status" aria-label="Đang tải phim" />;
}
export function EmptyState() {
  return (
    <div className="state">
      <Clapperboard />
      <h2>Chưa tìm thấy bộ phim phù hợp</h2>
      <p>Thử một tựa phim hoặc thể loại khác.</p>
    </div>
  );
}
export function ErrorState({ retry }: { retry: () => void }) {
  return (
    <div className="state" role="alert">
      <h2>Không thể tải dữ liệu</h2>
      <button onClick={retry}>Thử lại</button>
    </div>
  );
}
export function UserLayout() {
  return (
    <>
      <Outlet />
      <footer>
        <Link to="/discover">CineMatch</Link>
        <span>Được tạo cho những người yêu điện ảnh.</span>
        <Link to="/health">Trạng thái hệ thống</Link>
      </footer>
    </>
  );
}
export function AuthLayout() {
  const register = useLocation().pathname === "/register",
    navigate = useNavigate(),
    qc = useQueryClient(),
    [show, setShow] = useState(false),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [name, setName] = useState("");
  const auth = useMutation({
    mutationFn: async () => {
      if (register)
        await portal.post("/auth/register", {
          email,
          password,
          display_name: name,
        });
      return portal.post<{ access_token: string }>("/auth/login", {
        email,
        password,
      });
    },
    onSuccess: (data) => {
      qc.clear();
      useAuth.getState().setToken(data.access_token);
      navigate("/discover", { replace: true });
    },
  });
  return (
    <main className="auth">
      <Link to="/discover" className="brand">
        <Clapperboard /> CineMatch
      </Link>
      <div className="auth-card">
        <div className="tabs">
          <Link
            aria-current={!register ? "page" : undefined}
            to="/login"
            onClick={() => auth.reset()}
          >
            Đăng Nhập
          </Link>
          <Link
            aria-current={register ? "page" : undefined}
            to="/register"
            onClick={() => auth.reset()}
          >
            Tạo Tài Khoản
          </Link>
        </div>
        <h1>
          {register ? "Bắt đầu hành trình điện ảnh" : "Chào mừng trở lại."}
        </h1>
        <p className="muted">Bộ phim tiếp theo bạn yêu thích đang chờ.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            auth.mutate();
          }}
        >
          {register && (
            <label>
              Tên hiển thị
              <input
                value={name}
                maxLength={100}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                required
              />
            </label>
          )}
          <label>
            Email
            <input
              type="email"
              value={email}
              maxLength={320}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label>
            Mật khẩu
            <div className="password">
              <input
                aria-label="Mật khẩu"
                value={password}
                maxLength={128}
                minLength={register ? 12 : 1}
                onChange={(e) => setPassword(e.target.value)}
                type={show ? "text" : "password"}
                autoComplete={register ? "new-password" : "current-password"}
                required
              />
              <button
                type="button"
                aria-label={show ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                onClick={() => setShow(!show)}
              >
                {show ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>
          {register && <p className="muted">Tối thiểu 12 ký tự.</p>}
          {auth.isError && <p role="alert">{errorMessage(auth.error)}</p>}
          <button className="refresh" type="submit" disabled={auth.isPending}>
            {auth.isPending
              ? "Đang kết nối…"
              : register
                ? "Tạo tài khoản"
                : "Đăng nhập"}
          </button>
        </form>
      </div>
      <Link to="/discover">← Khám phá CineMatch</Link>
    </main>
  );
}
