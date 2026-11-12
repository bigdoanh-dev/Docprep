import { test, expect, type Page } from "@playwright/test";
import { passwordAccount } from "./support/passwordAccount";

async function headers(page: Page) {
  const token = await page.evaluate(
    () => JSON.parse(localStorage.getItem("yhdp.session")!).access_token,
  );
  return { Authorization: `Bearer ${token}` };
}

test("learner: password login, consent, learn, cards, exam, progress and chat availability", async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = [];
  let expectsDisabledAI = false;
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !(
        expectsDisabledAI &&
        /Failed to load resource: the server responded with a status of 503/.test(
          message.text(),
        )
      )
    )
      errors.push(message.text());
  });
  const health = await request.get("/api/health");
  const runtime = await health.json();
  test.skip(
    !["scripted", "disabled"].includes(runtime.model_provider),
    "Local acceptance uses scripted or disabled AI",
  );
  expect(runtime).toMatchObject({
    ok: true,
    mode: "real",
  });
  const unauthorized = await request.get("/api/v1/me");
  expect(unauthorized.status()).toBe(401);
  expect(unauthorized.headers()["content-type"]).toContain("application/json");
  const account = passwordAccount();
  await page.goto("/dang-nhap");
  await expect(page).toHaveTitle(/DocPrep/i);
  if (runtime.model_provider === "disabled") {
    await expect(page.locator(".demo-strip")).toHaveCount(0);
  } else {
    await expect(page.getByRole("note")).toContainText("AI mô phỏng");
  }
  await page
    .getByLabel("Tên đăng nhập", { exact: true })
    .fill(account.username);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
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
  await page.goto("/thi-thu");
  await page
    .getByRole("button", {
      name: form.module_id ? "Thi thử theo chuyên khoa" : "Thi thử tổng hợp",
      exact: false,
    })
    .click();
  if (form.module_id) {
    await page.getByRole("combobox").selectOption(form.module_id);
  }
  await page
    .getByRole("region", { name: form.title, exact: true })
    .getByRole("link", { name: /^(Bắt đầu thi|Làm bài đánh giá)$/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "Quy định đề thi thử" }),
  ).toBeVisible();
  const started = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/exams/${form.id}/attempts`) &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Bắt đầu", exact: true }).click();
  const startedResponse = await started;
  expect(startedResponse.ok()).toBeTruthy();
  const attempt = await startedResponse.json();
  await expect(page).toHaveURL(
    new RegExp(`/thi-thu/lam-bai/${attempt.attempt_id}$`),
  );
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
  const result = await get(`/attempts/${attempt.attempt_id}/results`);
  expect(result.submitted_at).toBeTruthy();
  expect(result.levels).toHaveLength(3);
  expect(result.specialties).toHaveLength(8);
  expect(
    result.issues_by_specialty.flatMap((g: { issues: unknown[] }) => g.issues),
  ).toHaveLength(54);
  await expect(
    page.getByRole("heading", { name: "Điểm mạnh & cần ôn", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Mức độ vận dụng", exact: true })
    .click();
  const resultLegend = page.getByRole("list", {
    name: "Chú giải theo mức độ vận dụng",
  });
  await expect(resultLegend.getByRole("button")).toHaveCount(3);
  for (const [index, level] of result.levels.entries()) {
    await expect(resultLegend.getByRole("button").nth(index)).toContainText(
      level.label_vi,
    );
    if (level.total)
      await expect(resultLegend.getByRole("button").nth(index)).toContainText(
        `${level.correct}/${level.total}`,
      );
  }
  const qid = attempt.questions[0].id;
  const review = await get(`/attempts/${attempt.attempt_id}/items/${qid}`);
  await page.goto(`/thi-thu/ket-qua/${attempt.attempt_id}/${qid}`);
  const classification = page.locator(".question-classification");
  await expect(classification).toContainText(review.bloom_label);
  await expect(classification).toContainText(review.module_name);
  if (review.core_issue_name)
    await expect(classification).toContainText(review.core_issue_name);
  await page.goto("/tien-do");
  await page.getByText("Phân tích chi tiết", { exact: true }).click();
  await page
    .getByRole("button", { name: "Mức độ vận dụng", exact: true })
    .click();
  const progressLegend = page.getByRole("list", {
    name: "Chú giải theo mức độ vận dụng",
  });
  await expect(progressLegend.getByRole("button")).toHaveCount(3);
  await expect(progressLegend.getByRole("button").nth(1)).toContainText(
    "Vận dụng",
  );
  await page
    .getByLabel("Xem mức độ vận dụng theo chuyên khoa", { exact: true })
    .selectOption("g2");
  await expect(progressLegend).toContainText("Chưa có dữ liệu");
  await expect(progressLegend).not.toContainText("câu đúng");
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
  expectsDisabledAI = runtime.model_provider === "disabled";
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();
  const chatResponse = await stream;
  if (expectsDisabledAI) {
    expect(chatResponse.status()).toBe(503);
    expect((await chatResponse.json()).error.code).toBe("ai_disabled");
    await expect(page.getByRole("alert")).toContainText("chưa được bật");
    await expect(page.getByRole("button", { name: /Nguồn 1:/ })).toHaveCount(0);
    await page.reload();
    await expect(
      page.getByRole("textbox", { name: "Câu hỏi của bạn" }),
    ).toBeEnabled();
  } else {
    expect(chatResponse.headers()["content-type"]).toContain(
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
    await page
      .getByRole("dialog")
      .getByRole("button", { name: /Đóng/ })
      .click();
    await page.reload();
    await expect(
      page.getByRole("button", { name: /Nguồn 1:/ }).first(),
    ).toBeVisible();
  }
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
    await page.getByLabel("Tên đăng nhập", { exact: true }).fill(email);
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
    const runtime = await (await page.request.get("/api/health")).json();
    if (runtime.model_provider === "disabled") {
      await expect(page.locator(".demo-strip")).toHaveCount(0);
    } else {
      await expect(page.locator(".demo-strip")).toContainText(
        "dữ liệu minh họa",
      );
    }
    await page.screenshot({
      path: testInfo.outputPath("alpha-dashboard.png"),
      animations: "disabled",
      fullPage: false,
    });
    expect(errors).toEqual([]);
  });
}
