import { test, expect } from "@playwright/test";
import { passwordAccount } from "./support/passwordAccount";

test("INT-001: live server streak, loading/error states and activity refresh", async ({
  page,
  request,
}, testInfo) => {
  test.skip(!process.env.PHASE1_URL, "Requires the real local backend");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("503"))
      errors.push(message.text());
  });
  const account = passwordAccount();
  await page.goto("/dang-nhap");
  await page
    .getByLabel("Tên đăng nhập", { exact: true })
    .fill(account.username);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Tôi đồng ý (bắt buộc)", exact: true })
    .check();
  await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
  await expect(page).toHaveURL(/chon-hoc-phan/);
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Bỏ qua, vào học ngay" }).click();
  const badge = page.locator(".streak-badge");
  await expect(badge).toHaveAccessibleName("Chuỗi ôn tập 0 ngày");
  const token = await page.evaluate(
    () => JSON.parse(localStorage.getItem("yhdp.session")!).access_token,
  );
  const headers = { Authorization: `Bearer ${token}` };
  expect(
    (await (await request.get("/api/v1/progress/rhythm", { headers })).json())
      .streak_days,
  ).toBe(0);
  // A real exam-start event is one of the existing backend study-day kinds.
  const attempt = await request.post("/api/v1/exams/de-thi-thu-1/attempts", {
    headers,
    data: {},
  });
  expect(attempt.ok()).toBeTruthy();
  await page.evaluate(() =>
    window.dispatchEvent(new Event("yhdp-learning-updated")),
  );
  await expect(badge).toHaveAccessibleName("Chuỗi ôn tập 1 ngày");
  const id = (await attempt.json()).attempt_id;
  expect(
    (await request.post(`/api/v1/attempts/${id}/submit`, { headers })).ok(),
  ).toBeTruthy();
  await page.reload();
  await expect(badge).toHaveAccessibleName("Chuỗi ôn tập 1 ngày");
  await page.screenshot({ path: testInfo.outputPath("streak-live.png") });

  // Only delay/failure are injected; success values above came from the real DB/API.
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/progress/rhythm", async (route) => {
    await pending;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "unavailable", message_vi: "Lỗi kiểm thử" },
      }),
    });
  });
  await page.reload();
  await expect(badge).toHaveAccessibleName("Đang tải chuỗi ôn tập");
  await expect(badge).toHaveText("…");
  release();
  await expect(badge).toHaveText("—");
  await expect(badge).toHaveAccessibleName(/Không tải được/);
  await page.unroute("**/api/v1/progress/rhythm");
  await page.route("**/api/v1/progress/rhythm", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
  );
  await page.reload();
  await expect(badge).toHaveAccessibleName(/Không tải được/);
  await expect(badge).toHaveText("—");
  await page.unroute("**/api/v1/progress/rhythm");
  await badge.click();
  await expect(badge).toHaveAccessibleName("Chuỗi ôn tập 1 ngày");
  expect(errors).toEqual([]);
});
