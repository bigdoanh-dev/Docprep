import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";

test("Phase 1: lost POST response retries the same turn, citations survive reload", async ({ page, request }) => {
  test.skip(!process.env.PHASE1_URL, "Requires the separate Phase 1 deployment");
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const code = execFileSync("docker", ["compose", "--env-file", ".env.phase1", "-f", "deploy/compose.phase1.yml",
    "run", "--rm", "--no-deps", "seed", "python", "-m", "seed.browser"], { encoding: "utf8" }).trim();
  await page.goto("/dang-nhap");
  await page.getByLabel("Mã kích hoạt", { exact: true }).fill(code);
  await page.getByRole("button", { name: "Kích hoạt và đăng nhập" }).click();
  await expect(page).toHaveURL(/dong-y/);
  await page.getByRole("checkbox", { name: "Tôi đồng ý (bắt buộc)", exact: true }).check();
  await page.getByRole("button", { name: "Tiếp tục", exact: true }).click();
  await expect(page).toHaveURL(/chon-hoc-phan/);
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Bỏ qua, vào học ngay" }).click();
  await expect(page).toHaveURL(/luyen-tap\/[^/]+$/);
  // Navigate with the same application route used by the main smoke.
  await page.goto("/hoi-dap");
  let dropped = false;
  const keys: string[] = [];
  await page.route("**/api/v1/chat/sessions/*/messages", async route => {
    if (route.request().method() !== "POST") return route.continue();
    keys.push(route.request().headers()["idempotency-key"]);
    if (!dropped) {
      dropped = true;
      await route.fetch(); // commit the real backend turn, then lose its HTTP response
      await route.abort("failed");
    } else await route.continue();
  });
  const composer = page.getByRole("textbox").last();
  await composer.fill("Tỷ lệ hiện mắc là gì?");
  await page.getByRole("button", { name: /Gửi/ }).click();
  await expect(page.getByRole("button", { name: /Nguồn 1:/ }).first()).toBeVisible({ timeout: 30000 });
  expect(keys.length).toBeGreaterThanOrEqual(2);
  expect(new Set(keys).size).toBe(1);
  await page.reload();
  await expect(page.getByRole("button", { name: /Nguồn 1:/ }).first()).toBeVisible();
  const token = await page.evaluate(() => JSON.parse(localStorage.getItem("yhdp.session")!).access_token);
  const sessions = await request.get("/api/v1/chat/sessions", { headers: { Authorization: `Bearer ${token}` } });
  const sid = (await sessions.json()).items[0].id;
  const messages = await request.get(`/api/v1/chat/sessions/${sid}/messages`, { headers: { Authorization: `Bearer ${token}` } });
  const assistants = (await messages.json()).items.filter((m: { role: string }) => m.role === "assistant");
  expect(assistants).toHaveLength(1);
  expect(assistants[0].citations.length).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});
