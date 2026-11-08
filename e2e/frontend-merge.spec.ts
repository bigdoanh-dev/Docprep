import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

const examples = JSON.parse(
  readFileSync(
    new URL("../src/lib/demo/examples.json", import.meta.url),
    "utf8",
  ),
);

async function runtime(page: Page) {
  await page.route("**/api/health", (route) =>
    route.fulfill({
      json: {
        ok: true,
        mode: "real",
        model_provider: "scripted",
        demo_content: true,
      },
    }),
  );
}

async function startDemo(page: Page) {
  await runtime(page);
  await page.goto("/dang-nhap");
  await expect(page.getByRole("note")).toContainText("AI mô phỏng");
  await page.getByRole("button", { name: "Dùng dữ liệu trải nghiệm" }).click();
  await page.getByRole("button", { name: "Người học", exact: true }).click();
  await expect(page).toHaveURL(/dong-y/);
  await expect(
    page.getByRole("navigation", { name: "Điều hướng chính" }),
  ).toHaveCount(0);
  await page
    .getByRole("checkbox", { name: "Tôi đồng ý (bắt buộc)", exact: true })
    .check();
  await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
  await expect(page).toHaveURL(/chon-hoc-phan/);
  await expect(
    page.getByRole("list", { name: "Tiến trình thiết lập" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Bỏ qua, vào học ngay" }).click();
  await expect(page).toHaveURL(/luyen-tap\/[^/]+$/);
}

test("merged frontend: demo onboarding, exams and 54-issue progress", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await startDemo(page);
  await page
    .getByRole("link", { name: "Tiến độ", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Thống kê học tập" }),
  ).toBeVisible();
  await page.getByText("Phân tích chi tiết", { exact: true }).click();
  await page
    .getByLabel("Đề mục chuyên khoa", { exact: true })
    .selectOption("g1");
  await expect(
    page.getByRole("list", { name: /^Chú giải theo vấn đề ·/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Học tập", exact: true }).click();
  await page.getByRole("link", { name: "Thi thử", exact: true }).click();
  await page
    .getByRole("button", { name: "Thi thử tổng hợp", exact: false })
    .click();
  const form = page.getByRole("region", {
    name: "Đề thi demo · 54 vấn đề",
    exact: true,
  });
  await expect(form).toBeVisible();
  await form.getByRole("link", { name: "Làm bài mới", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Quy định đề thi thử" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Bắt đầu", exact: true }).click();
  await expect(page).toHaveURL(/thi-thu\/lam-bai\/\d+$/);
  await expect(
    page.getByRole("radiogroup", { name: "Các phương án" }),
  ).toBeVisible();
  await page.getByRole("radio").first().click();
  await page.getByRole("button", { name: "Nộp bài", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Nộp bài", exact: true })
    .click();
  await expect(page).toHaveURL(/thi-thu\/ket-qua\/\d+$/);
  expect(errors).toEqual([]);
});

test("merged frontend: Alpha exam API without optional classification fields", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await runtime(page);
  await page.route("**/api/v1/me", (route) =>
    route.fulfill({
      json: { ...examples.Me, diagnostic_prompt_dismissed: true },
    }),
  );
  // This is the Alpha response shape: module_id/module_name are absent.
  await page.route("**/api/v1/exams", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: "alpha-legacy",
            title: "Đề Alpha",
            kind: "demo_short",
            n_questions: 5,
            minutes: 5,
            attempts_left: null,
            last: null,
            open_attempt_id: null,
            open_remaining_s: null,
            history: [],
            plan: null,
          },
        ],
      },
    }),
  );
  await page.goto("/dang-nhap");
  await page.evaluate(() => {
    localStorage.setItem(
      "yhdp.actor.v1",
      JSON.stringify({
        role: "learner",
        mode: "live",
        name: "Alpha",
        id: "HV-000123",
      }),
    );
    localStorage.setItem(
      "yhdp.session",
      JSON.stringify({
        access_token: "frontend-test",
        refresh_token: "frontend-test-refresh",
      }),
    );
  });
  await page.goto("/thi-thu");
  await expect(
    page.getByRole("link", { name: "Xem nhịp học từ máy chủ" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Thi thử tổng hợp", exact: false })
    .click();
  await page
    .getByRole("region", { name: "Đề Alpha", exact: true })
    .getByRole("link", { name: "Bắt đầu thi", exact: true })
    .click();
  await expect(page).toHaveURL(/alpha-legacy\/quy-dinh\?mode=combined$/);
  await expect(
    page.getByRole("heading", { name: "Đề Alpha", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
