import { expect, test, type Page } from "@playwright/test";
test.use({ reducedMotion: "reduce" });
const movie = {
  id: 1,
  title: "Interstellar",
  original_title: "Interstellar Original",
  synopsis: "A journey across the stars.",
  release_year: 2014,
  runtime_minutes: 169,
  poster_url: null,
  trailer_youtube_id: "zSWdZVtXT7E",
  genres: [{ id: 1, name: "Sci-Fi" }],
  average_rating: 4.45,
  rating_count: 12,
  popularity: 100,
  comment_count: 1,
};
async function mock(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname,
      method = route.request().method();
    let data: unknown = {};
    if (path.endsWith("/auth/login")) data = { access_token: "test-token" };
    else if (path.endsWith("/genres")) data = [{ id: 1, name: "Sci-Fi" }];
    else if (path.endsWith("/recommendations/me"))
      data = {
        items: [
          {
            movie_id: 1,
            rank: 1,
            method: "hybrid",
            ranking_score: 0.98,
            predicted_rating: 4.9,
          },
        ],
        status: "ready",
        generated_at: "2026-11-15T12:00:00Z",
        algorithm_version: "hybrid-v1",
      };
    else if (path.endsWith("/recommendations/refresh"))
      data = { status: "scheduled" };
    else if (path.endsWith("/interactions/movies/1"))
      data = {
        rating: null,
        watchlist: false,
        favorite: false,
        watched: false,
      };
    else if (path.endsWith("/comments"))
      data = {
        items: [
          {
            id: 1,
            movie_id: 1,
            username: "Linh",
            body: "Beautiful film",
            created_at: "2026-11-15T12:00:00Z",
            likes: 2,
            liked: false,
          },
        ],
        page: 1,
        page_size: 20,
        total: 1,
      };
    else if (path.endsWith("/movies/1")) data = movie;
    else if (path.endsWith("/movies"))
      data = {
        items: [movie],
        page: Number(url.searchParams.get("page") || 1),
        page_size: 5,
        total: 12,
      };
    if (
      method === "DELETE" ||
      path.endsWith("/like") ||
      path.endsWith("/watchlist")
    )
      return route.fulfill({ status: 204 });
    await route.fulfill({ json: { data } });
  });
}
async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill("film@example.com");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("valid password");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/discover/);
}
test("auth routes are clean and registration tab follows URL", async ({
  page,
}) => {
  await page.goto("/register");
  await expect(page.getByLabel("Tên hiển thị")).toBeVisible();
  await expect(page.locator(".movie")).toHaveCount(0);
  await page.getByRole("link", { name: "Đăng Nhập", exact: true }).click();
  await expect(page).toHaveURL(/login/);
  await expect(page.getByLabel("Tên hiển thị")).toHaveCount(0);
});
test("discovery filters, pagination, inline drawer and movie route", async ({
  page,
}) => {
  await mock(page);
  await page.goto("/discover");
  await expect(
    page.getByRole("heading", { name: /Interstellar/ }),
  ).toBeVisible();
  const search = page.waitForRequest(
    (r) =>
      r.url().includes("/movies?") &&
      new URL(r.url()).searchParams.get("q") === "stars",
  );
  await page.getByLabel("Tìm kiếm phim").fill("stars");
  await search;
  await page.getByLabel("Thể loại", { exact: true }).selectOption("1");
  await page.getByLabel("Năm phát hành").fill("2014");
  await page.getByLabel("Điểm tối thiểu").selectOption("4");
  await page.getByLabel("Sắp xếp", { exact: true }).selectOption("rating");
  await expect.poll(() => page.locator(".movie").count()).toBe(1);
  const next = page.waitForRequest(
    (r) =>
      r.url().includes("/movies?") &&
      new URL(r.url()).searchParams.get("page") === "2",
  );
  await page.getByRole("button", { name: "Sau →", exact: true }).click();
  await next;
  const resized = page.waitForRequest(
    (r) =>
      r.url().includes("/movies?") &&
      new URL(r.url()).searchParams.get("page_size") === "5",
  );
  await page.getByLabel("Phim mỗi trang").selectOption("5");
  await resized;
  await page
    .getByRole("button", { name: "Insights, Trailer & Bình luận" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Official Trailer" }),
  ).toBeVisible();
  await expect(page.locator("iframe")).toHaveAttribute(
    "src",
    /youtube-nocookie/,
  );
  await page.screenshot({
    path: "test-results/portal-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Trả lời", exact: true }).click();
  await expect(page.getByLabel("Bình luận", { exact: true })).toHaveValue(
    "@Linh ",
  );
  await expect(page.getByLabel("Bình luận", { exact: true })).toBeFocused();
  await page.getByRole("link", { name: "Interstellar", exact: true }).click();
  await expect(page).toHaveURL("/movies/1");
  await expect(
    page.getByRole("heading", { name: "Official Trailer" }),
  ).toBeVisible();
});
test("optimistic watchlist rolls back on failure and rating uses POST then PUT", async ({
  page,
}) => {
  await mock(page);
  await login(page);
  await page.route("**/api/v1/interactions/watchlist", async (route) => {
    await new Promise((r) => setTimeout(r, 400));
    await route.fulfill({ status: 500, json: { message: "Try again" } });
  });
  await page.getByRole("button", { name: "Lưu kho phim", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Đã lưu", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("button", { name: "Lưu kho phim", exact: true }),
  ).toBeVisible();
  let value: number | null = null;
  await page.route("**/api/v1/interactions/movies/1", (route) =>
    route.fulfill({
      json: {
        data: {
          rating: value,
          watchlist: false,
          favorite: false,
          watched: false,
        },
      },
    }),
  );
  await page.route("**/api/v1/interactions/rating", async (route) => {
    expect(route.request().method()).toBe("POST");
    value = route.request().postDataJSON().value;
    await route.fulfill({ json: { data: { value } } });
  });
  await page
    .getByRole("button", { name: "Rate 4.5 stars", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Rate 4.5 stars", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("button", { name: "Rate 4 stars", exact: true }),
  ).toBeEnabled();
  const put = page.waitForRequest(
    (r) => r.url().endsWith("/rating/1") && r.method() === "PUT",
  );
  await page.getByRole("button", { name: "Rate 4 stars", exact: true }).click();
  await put;
});
test("mobile discovery stays inside viewport", async ({ page }) => {
  await mock(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator(".movie")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/portal-mobile.png",
    fullPage: true,
  });
});

test("refresh waits for a new generation and comment hearts update optimistically", async ({
  page,
}) => {
  await mock(page);
  await login(page);
  await expect(page.getByText("98% Khớp gu", { exact: true })).toBeVisible();
  await page.route("**/api/v1/recommendations/me?*", (route) =>
    route.fulfill({
      json: {
        data: {
          items: [
            {
              movie_id: 1,
              rank: 1,
              method: "hybrid",
              ranking_score: 0.97,
              predicted_rating: 4.8,
            },
          ],
          status: "ready",
          generated_at: "2026-11-15T13:00:00Z",
          algorithm_version: "hybrid-v1",
        },
      },
    }),
  );
  await page.getByRole("button", { name: "Gợi ý mới", exact: true }).click();
  await expect(page.getByRole("status", {name:"Thông báo"})).toContainText(
    "Ma trận gợi ý đã được tính toán lại.",
  );
  await page
    .getByRole("button", { name: "Insights, Trailer & Bình luận" })
    .click();
  await page.route("**/api/v1/comments/1/like", async (route) => {
    await new Promise((r) => setTimeout(r, 400));
    await route.fulfill({ status: 500, json: { message: "Like failed" } });
  });
  const heart = page.getByRole("button", { name: "Thích bình luận của Linh" });
  await heart.click();
  await expect(heart).toHaveAttribute("aria-pressed", "true");
  await expect(heart).toContainText("3");
  await expect(heart).toHaveAttribute("aria-pressed", "false");
  await expect(heart).toContainText("2");
  const posted = page.waitForRequest(
    (r) => r.url().endsWith("/movies/1/comments") && r.method() === "POST",
  );
  await page.getByLabel("Bình luận", { exact: true }).fill("Great film!");
  await page.getByRole("button", { name: "Gửi bình luận" }).click();
  expect((await posted).postDataJSON()).toEqual({ body: "Great film!" });
});
