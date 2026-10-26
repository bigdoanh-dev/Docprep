import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

const root = process.cwd();
const python = path.join(
  root,
  "backend",
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);

async function headers(page: Page) {
  const token = await page.evaluate(
    () => JSON.parse(localStorage.getItem("yhdp.session")!).access_token,
  );
  return { Authorization: `Bearer ${token}` };
}

test("learner: activate, consent, learn, cards, exam, progress and cited scripted chat", async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  const health = await request.get("/api/health");
  expect(await health.json()).toMatchObject({
    ok: true,
    mode: "real",
    model_provider: "scripted",
  });
  const unauthorized = await request.get("/api/v1/me");
  expect(unauthorized.status()).toBe(401);
  expect(unauthorized.headers()["content-type"]).toContain("application/json");
  const code = execFileSync(python, ["-m", "seed.browser"], {
    cwd: path.join(root, "backend"),
    encoding: "utf8",
  }).trim();
  await page.goto("/dang-nhap");
  await expect(page).toHaveTitle(/DocPrep/i);
  await expect(page.getByRole("note")).toContainText("AI mô phỏng");
  await page.getByLabel("Mã kích hoạt", { exact: true }).fill(code);
  await page.getByRole("button", { name: "Kích hoạt và đăng nhập" }).click();
  await expect(page).toHaveURL(/dong-y/);
  await page
    .getByRole("checkbox", { name: "Tôi đồng ý (bắt buộc)", exact: true })
    .check();
  await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
  await expect(page).toHaveURL(/chon-hoc-phan/);
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Bỏ qua, vào học ngay" }).click();
  await expect(page).toHaveURL(/luyen-tap\/[^/]+$/);
  const unitId = new URL(page.url()).pathname.split("/").at(-1)!;
  const auth = await headers(page);
  const get = async (route: string) => {
    const response = await request.get(`/api/v1${route}`, { headers: auth });
    expect(response.ok(), route).toBeTruthy();
    return response.json();
  };
  let unit = await get(`/units/${unitId}/next`);
  while (!unit.done && unit.item.kind !== "quiz") {
    const advanced = page.waitForResponse(
      (r) =>
        r.url().endsWith(`/units/${unitId}/advance`) &&
        r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
    expect((await advanced).ok()).toBeTruthy();
    unit = await get(`/units/${unitId}/next`);
  }
  expect(unit.done).toBeFalsy();
  // q-dt-01's b option is deliberately wrong: the resulting card is part of this acceptance path.
  const option = unit.item.question.options.findIndex(
    (o: { key: string }) => o.key === "b",
  );
  await page
    .getByRole("radiogroup", { name: "Các phương án" })
    .getByRole("radio")
    .nth(option)
    .click();
  const graded = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/units/${unitId}/responses`) &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Kiểm tra", exact: true }).click();
  expect(await (await graded).json()).toMatchObject({
    correct: false,
    card_created: true,
  });
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Tiếp tục", exact: true }),
  ).toBeVisible();
  unit = await get(`/units/${unitId}/next`);
  expect(unit.item.chosen).toBe("b");
  // Finish the remaining unit using rendered controls, including every response/advance.
  for (let step = 0; step < 30; step++) {
    if (unit.done) break;
    if (unit.item.kind === "quiz" && !unit.item.feedback) {
      await page
        .getByRole("radiogroup", { name: "Các phương án" })
        .getByRole("radio")
        .first()
        .click();
      const answer = page.waitForResponse(
        (r) =>
          r.url().endsWith(`/units/${unitId}/responses`) &&
          r.request().method() === "POST",
      );
      await page.getByRole("button", { name: "Kiểm tra", exact: true }).click();
      expect((await answer).ok()).toBeTruthy();
    }
    const advanced = page.waitForResponse(
      (r) =>
        r.url().endsWith(`/units/${unitId}/advance`) &&
        r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
    const advancedResponse = await advanced;
    expect(advancedResponse.ok()).toBeTruthy();
    unit = await advancedResponse.json();
  }
  expect(unit.done).toBeTruthy();

  await page.goto("/luyen-tap/on-the");
  await page.getByRole("button", { name: "Hiện đáp án", exact: true }).click();
  const reviewed = page.waitForResponse(
    (r) =>
      /\/cards\/\d+\/reviews$/.test(r.url()) && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: /Tốt/ }).click();
  expect((await reviewed).ok()).toBeTruthy();

  const forms = await get("/exams");
  const form =
    forms.items.find((f: { kind: string }) => f.kind === "demo_short") ??
    forms.items[0];
  const started = await request.post(`/api/v1/exams/${form.id}/attempts`, {
    headers: auth,
    data: {},
  });
  expect(started.ok()).toBeTruthy();
  const attempt = await started.json();
  await page.goto(`/thi-thu/lam-bai/${attempt.attempt_id}`);
  const saved = page.waitForResponse(
    (r) =>
      r.url().includes(`/attempts/${attempt.attempt_id}/answers/`) &&
      r.request().method() === "PUT",
  );
  await page
    .getByRole("radiogroup", { name: "Các phương án" })
    .getByRole("radio")
    .first()
    .click();
  expect((await saved).ok()).toBeTruthy();
  await page.reload();
  expect(
    Object.keys((await get(`/attempts/${attempt.attempt_id}`)).answers),
  ).toHaveLength(1);
  await page.getByRole("button", { name: "Nộp bài", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Nộp bài", exact: true })
    .click();
  await expect(page).toHaveURL(/thi-thu\/ket-qua/);
  expect(
    (await get(`/attempts/${attempt.attempt_id}/results`)).submitted_at,
  ).toBeTruthy();
  await page.goto("/tien-do/nhip-hoc");
  await expect(
    page.getByRole("heading", { name: "Thống kê học tập" }),
  ).toBeVisible();
  expect((await get("/progress/rhythm")).heatmap).toHaveLength(56);
  await page.goto("/hoi-dap");
  await page
    .getByRole("textbox", { name: "Câu hỏi của bạn" })
    .fill("Tỷ lệ hiện mắc là gì?");
  const stream = page.waitForResponse(
    (r) =>
      /\/chat\/sessions\/\d+\/messages$/.test(r.url()) &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();
  expect((await stream).headers()["content-type"]).toContain(
    "text/event-stream",
  );
  await expect(
    page.getByRole("button", { name: /Nguồn 1:/ }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Nguồn 1:/ })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText("Tài liệu demo");
  await page.getByRole("dialog").getByRole("button", { name: /Đóng/ }).click();
  await page.reload();
  await expect(
    page.getByRole("button", { name: /Nguồn 1:/ }).first(),
  ).toBeVisible();
  expect(await page.locator("vite-error-overlay").count()).toBe(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: testInfo.outputPath("alpha-chat.png"),
    animations: "disabled",
    fullPage: false,
  });
  expect(errors).toEqual([]);
});

for (const email of ["viewer@alpha.local", "admin@alpha.local"]) {
  test(`staff ${email} dashboard reads the real API`, async ({
    page,
  }, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error" || message.type() === "warning")
        errors.push(message.text());
    });
    await page.goto("/dang-nhap");
    await page.getByRole("button", { name: "Cán bộ", exact: true }).click();
    await page.getByLabel("Email công vụ").fill(email);
    await page.getByLabel("Mật khẩu", { exact: true }).fill("AlphaLocal2026!");
    const overview = page.waitForResponse((r) =>
      r.url().includes("/api/v1/admin/dashboard/overview"),
    );
    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
    if (email.startsWith("admin")) {
      await page.getByRole("link", { name: "Tổng hợp", exact: true }).click();
    }
    const overviewResponse = await overview;
    expect(overviewResponse.ok()).toBeTruthy();
    const data = await overviewResponse.json();
    expect(data.suppressed).toBe(false);
    expect(data.kpis.accounts_activated).toBeGreaterThanOrEqual(10);
    await expect(
      page.getByRole("heading", { name: "Báo cáo tổng quan" }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Chỉ số chính" }),
    ).toBeVisible();
    await expect(
      page.getByText("Học viên hoạt động", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0);
    await expect(page.getByRole("note")).toContainText("dữ liệu minh họa");
    await page.screenshot({
      path: testInfo.outputPath("alpha-dashboard.png"),
      animations: "disabled",
      fullPage: false,
    });
    expect(errors).toEqual([]);
  });
}
