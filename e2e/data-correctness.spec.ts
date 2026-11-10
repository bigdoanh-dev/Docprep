import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

const examples = JSON.parse(
  readFileSync(
    new URL("../src/lib/demo/examples.json", import.meta.url),
    "utf8",
  ),
);
const issueName = "Tên vấn đề được duyệt từ API";
const moduleName = "Chuyên khoa được duyệt từ API";
const levels = [
  { level: 1, label_vi: "Nhớ, Hiểu", correct: 0, total: 0 },
  { level: 2, label_vi: "Vận dụng", correct: 1, total: 1 },
  { level: 3, label_vi: "Phân tích, Đánh giá", correct: 0, total: 0 },
];

async function setRuntime(page: Page) {
  await page.route("**/api/health", (route) =>
    route.fulfill({
      json: {
        ok: true,
        mode: "real",
        service: "chat",
        model_provider: "disabled",
        demo_content: true,
      },
    }),
  );
}

async function useLiveFixture(page: Page) {
  await setRuntime(page);
  await page.route("**/api/v1/me", (route) =>
    route.fulfill({
      json: { ...examples.Me, diagnostic_prompt_dismissed: true },
    }),
  );
  await page.addInitScript(() => {
    localStorage.setItem(
      "yhdp.actor.v1",
      JSON.stringify({
        role: "learner",
        mode: "live",
        name: "Test",
        id: "HV-000123",
      }),
    );
    localStorage.setItem(
      "yhdp.session",
      JSON.stringify({
        access_token: "frontend-contract-test",
        refresh_token: "frontend-contract-refresh",
      }),
    );
  });
}

function errorsOn(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  return errors;
}

test("question classification keeps API names and falls back only when absent", async ({
  page,
}) => {
  const errors = errorsOn(page);
  await useLiveFixture(page);
  let apiName: string | null = issueName;
  await page.route("**/api/v1/attempts/901/results", (route) =>
    route.fulfill({
      json: {
        attempt_id: 901,
        items: [{ question_id: "q-review", topic: "Test", status: "ok" }],
      },
    }),
  );
  await page.route("**/api/v1/attempts/901/items/q-review", (route) =>
    route.fulfill({
      json: {
        n: 1,
        total: 1,
        question_id: "q-review",
        stem: "Câu hỏi kiểm tra tên từ API",
        options: [{ key: "a", text: "Phương án A", is_correct: true }],
        chosen: "a",
        explanation: "Giải thích minh họa",
        rationales: {},
        citations: [],
        module_id: "g4",
        module_name: moduleName,
        core_issue_id: 24,
        core_issue_name: apiName,
        difficulty_label: "de",
        bloom_level: 2,
        bloom_label: "Vận dụng",
      },
    }),
  );
  await page.goto("/thi-thu/ket-qua/901/q-review");
  await expect(page).toHaveTitle(/DocPrep/);
  await expect(
    page.getByText("Giải thích của chuyên gia", { exact: true }),
  ).toHaveCount(0);
  const classification = page.getByRole("definition");
  await expect(classification.filter({ hasText: issueName })).toHaveCount(1);
  await expect(page.getByText(moduleName, { exact: true })).toBeVisible();
  await expect(
    page.getByText("Hội chứng viêm long đường hô hấp trên", { exact: true }),
  ).toHaveCount(0);
  apiName = null;
  await page.reload();
  await expect(
    page.getByText("Hội chứng viêm long đường hô hấp trên", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("progress uses API issue names and membership in its chart and legend", async ({
  page,
}, testInfo) => {
  const errors = errorsOn(page);
  await useLiveFixture(page);
  await page.route("**/api/v1/progress/skills?*", (route) =>
    route.fulfill({
      json: {
        ...examples.ProgressSkills,
        levels,
        specialties: [
          { module_id: "g4", name: moduleName, correct: 1, total: 1 },
        ],
        bloom_by_specialty: [{ module_id: "g4", name: moduleName, levels }],
        issues_by_specialty: [
          {
            module_id: "g4",
            name: moduleName,
            issues: [
              { issue_id: 24, name: issueName, correct: 1, total: 1 },
              {
                issue_id: 999,
                name: "Vấn đề mới từ API",
                correct: 0,
                total: 0,
              },
            ],
          },
        ],
      },
    }),
  );
  await page.goto("/tien-do");
  await page.getByText("Phân tích chi tiết", { exact: true }).click();
  const filter = page.getByLabel("Đề mục chuyên khoa", { exact: true });
  await expect(filter.locator('option[value="g4"]')).toContainText(moduleName);
  await filter.selectOption("g4");
  const legend = page.getByRole("list", {
    name: `Chú giải theo vấn đề · ${moduleName}`,
  });
  await expect(legend.getByRole("listitem")).toHaveCount(2);
  await expect(
    legend.getByRole("button", { name: new RegExp(issueName) }),
  ).toContainText("1/1 câu đúng");
  await expect(
    legend.getByRole("button", { name: /Vấn đề mới từ API/ }),
  ).toContainText("Chưa có dữ liệu");
  await expect(
    page.getByRole("button", { name: `${issueName}: 100% đúng, 1/1 câu` }),
  ).toBeVisible();
  await legend.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("api-names.png") });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("demo repairs saved assessments without losing history and leaves blanks unassessed", async ({
  page,
}, testInfo) => {
  const errors = errorsOn(page);
  await setRuntime(page);
  await page.goto("/dang-nhap");
  await page.getByRole("button", { name: "Dùng dữ liệu trải nghiệm" }).click();
  await page.getByRole("button", { name: "Người học", exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Tôi đồng ý (bắt buộc)", exact: true })
    .check();
  await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
  await page.getByRole("button", { name: "Bỏ qua, vào học ngay" }).click();
  await expect(page).toHaveURL(/luyen-tap\/[^/]+$/);
  const before = await page.evaluate(() => {
    const s = JSON.parse(localStorage.getItem("yhdp.demo.v2")!);
    delete s.exam_assessment_version;
    s.me.display_name = "Hồ sơ demo cần giữ";
    for (const a of s.attempts) {
      a.results.levels[0].total = a.results.total; // Simulate the old cached assessment.
    }
    localStorage.setItem("yhdp.demo.v2", JSON.stringify(s));
    return s.attempts.map((a: any) => ({
      id: a.attempt_id,
      score: a.results.score,
      answers: a.answers,
    }));
  });
  // Demo login is intentionally session-local; navigate within the SPA to reopen saved data.
  await page
    .getByRole("link", { name: "Tiến độ", exact: true })
    .first()
    .click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          JSON.parse(localStorage.getItem("yhdp.demo.v2")!)
            .exam_assessment_version,
      ),
    )
    .toBe(1);
  const after = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("yhdp.demo.v2")!),
  );
  expect(after.me.display_name).toBe("Hồ sơ demo cần giữ");
  expect(
    after.attempts.map((a: any) => ({
      id: a.attempt_id,
      score: a.results.score,
      answers: a.answers,
    })),
  ).toEqual(before);
  for (const a of after.attempts) {
    expect(
      a.results.levels.reduce((sum: number, l: any) => sum + l.total, 0),
    ).toBe(Object.keys(a.answers).length);
  }
  await page.getByRole("link", { name: "Học tập", exact: true }).click();
  await page.getByRole("link", { name: "Thi thử", exact: true }).click();
  await page
    .getByRole("button", { name: "Thi thử tổng hợp", exact: false })
    .click();
  await page
    .getByRole("region", { name: "Đề thi thử tổng hợp ngắn", exact: true })
    .getByRole("link", { name: "Bắt đầu thi", exact: true })
    .click();
  await page.getByRole("button", { name: "Bắt đầu", exact: true }).click();
  await expect(
    page.getByRole("radiogroup", { name: "Các phương án" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Nộp bài", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Nộp bài", exact: true })
    .click();
  await expect(page).toHaveURL(/thi-thu\/ket-qua\/\d+$/);
  const legend = page.getByRole("list", { name: "Chú giải theo chuyên khoa" });
  await expect(
    legend.getByText("Chưa có dữ liệu", { exact: true }),
  ).toHaveCount(8);
  const final = await page.evaluate(
    () => JSON.parse(localStorage.getItem("yhdp.demo.v2")!).attempts[0],
  );
  expect(final.results.blank).toBe(10);
  expect(final.results.score).toBe(0);
  expect(final.results.total).toBe(10);
  expect(final.results.levels.every((l: any) => l.total === 0)).toBeTruthy();
  await page.getByRole("link", { name: "Quay lại danh sách đề" }).click();
  await page
    .getByRole("button", { name: "Thi thử tổng hợp", exact: false })
    .click();
  await page
    .getByRole("region", { name: "Đề thi thử tổng hợp ngắn", exact: true })
    .getByRole("link", { name: /Xem kết quả$/ })
    .click();
  await expect(
    legend.getByText("Chưa có dữ liệu", { exact: true }),
  ).toHaveCount(8);
  await legend.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("demo-blanks.png") });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  expect(await page.locator("vite-error-overlay").count()).toBe(0);
  expect(errors).toEqual([]);
});
