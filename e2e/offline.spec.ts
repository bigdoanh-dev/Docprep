import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";

test("disabled AI: real business API works and chat fails clearly without a fabricated answer", async ({ page, request }) => {
  test.skip(!process.env.PHASE1_URL, "Requires the isolated Phase 1 deployment");
  const health = await (await request.get("/api/health")).json();
  test.skip(health.model_provider !== "disabled", "Only the generation-disabled profile");
  const code = execFileSync("docker", ["compose", "--env-file", ".env.phase1", "-f", "deploy/compose.phase1.yml",
    "run", "--rm", "--no-deps", "seed", "python", "-m", "seed.browser"], { encoding: "utf8" }).trim();
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto("/dang-nhap");
  await expect(page.getByRole("note")).toContainText("AI đang tắt");
  await page.getByLabel("Mã kích hoạt", { exact: true }).fill(code);
  await page.getByRole("button", { name: "Kích hoạt và đăng nhập" }).click();
  await expect(page).toHaveURL(/dong-y/);
  await page.getByRole("checkbox", { name: "Tôi đồng ý (bắt buộc)", exact: true }).check();
  await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
  await expect(page).toHaveURL(/chon-hoc-phan/);
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Bỏ qua, vào học ngay" }).click();
  await expect(page).toHaveURL(/luyen-tap\/[^/]+$/);
  await page.goto("/");
  await expect(page.getByRole("note")).toContainText("AI đang tắt");
  const auth = await page.evaluate(() => ({ Authorization: `Bearer ${JSON.parse(localStorage.getItem("yhdp.session")!).access_token}` }));
  expect((await request.get("/api/v1/home", { headers: auth })).ok()).toBeTruthy();
  expect((await request.get("/api/v1/chat/sessions", { headers: auth })).ok()).toBeTruthy();
  await page.goto("/hoi-dap");
  await page.getByRole("textbox", { name: "Câu hỏi của bạn" }).fill("Tỷ lệ hiện mắc là gì?");
  const rejected = page.waitForResponse(r => /\/chat\/sessions\/\d+\/messages$/.test(r.url()) && r.request().method() === "POST");
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();
  const response = await rejected;
  expect(response.status()).toBe(503);
  expect((await response.json()).error.code).toBe("ai_disabled");
  await expect(page.getByRole("alert")).toContainText("chưa được bật");
  await expect(page.getByRole("textbox", { name: "Câu hỏi của bạn" })).toBeEnabled();
  await expect(page.getByRole("button", { name: /Nguồn 1:/ })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("textbox", { name: "Câu hỏi của bạn" })).toBeEnabled();
  // A Home topic opens the new tutor popup and sends exactly once, including in Vite StrictMode.
  await page.goto("/");
  let created = 0;
  const countSessions = (r: import('@playwright/test').Request) => {
    if (r.url().endsWith('/api/v1/chat/sessions') && r.method() === 'POST') created++;
  };
  page.on('request', countSessions);
  const autoReply = page.waitForResponse(r => /\/chat\/sessions\/\d+\/messages$/.test(r.url()) && r.request().method() === 'POST');
  await page.getByRole('button', { name: /^Hỏi gia sư:/ }).first().click();
  expect((await autoReply).status()).toBe(503);
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('chưa được bật');
  expect(created).toBe(1);
  page.off('request', countSessions);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  expect(errors).toEqual([]);
});
