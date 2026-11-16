import { test, expect } from "@playwright/test";

test("content reviewer: source, proposal, approvals, release and reload", async ({
  page,
}, testInfo) => {
  test.skip(
    !process.env.CONTENT_E2E_URL || !process.env.CONTENT_QA_API_URL,
    "Explicit content QA environment required; never mutate the live workspace",
  );
  const base = process.env.CONTENT_E2E_URL!;
  const backend = process.env.CONTENT_QA_API_URL!;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // Real isolated API/database behind the same reviewer build; no fabricated API responses.
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api/, "");
    await route.fulfill({
      response: await route.fetch({
        url: backend + path + new URL(route.request().url()).search,
      }),
    });
  });
  await page.goto(base);
  await expect(page).toHaveTitle(/Kho tài liệu/);
  await page.getByLabel("Tên đăng nhập", { exact: true }).fill("reviewer.e2e");
  await page
    .getByLabel("Mật khẩu", { exact: true })
    .fill(process.env.CONTENT_E2E_PASSWORD!);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Biên soạn tài liệu YHDP" }),
  ).toBeVisible();
  const token = await page.evaluate(
    () =>
      JSON.parse(sessionStorage.getItem("content.session.v1")!).access_token,
  );
  const before = await (
    await page.request.get(backend + "/v1/chunks?classification=classified", {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json();
  await page.getByLabel("Trạng thái phân loại").selectOption("unclassified");
  await page.locator(".chunk-link").first().click();
  const detail = page.getByRole("region", { name: "Chi tiết chunk" });
  await expect(
    detail.getByText(/Dữ liệu dẫn xuất; chưa kèm file gốc/),
  ).toBeVisible();
  await detail
    .getByLabel("Lý do phân loại")
    .fill("Automated QA: proposal only, not clinical approval.");
  const proposed = page.waitForResponse(
    (r) => r.url().endsWith("/tags") && r.request().method() === "POST",
  );
  await detail.getByRole("button", { name: "Lưu đề xuất nhãn" }).click();
  expect((await proposed).status()).toBe(200);
  await expect(detail.getByText(/Version thao tác: 2/)).toBeVisible();
  await detail
    .getByLabel("Nhận xét / nội dung đã kiểm tra")
    .fill(
      "Automated isolated QA: classification decision, not expert evaluation.",
    );
  await detail
    .getByRole("button", { name: "Xác nhận phân loại", exact: true })
    .click();
  await expect(detail.getByText(/Version thao tác: 3/)).toBeVisible();
  await expect(detail.locator(".badges")).toContainText("Đã phân loại rõ ràng");
  await expect(detail.locator(".badges")).toContainText("Chờ duyệt nội dung");
  await detail
    .getByLabel("Nhận xét / nội dung đã kiểm tra")
    .fill("Automated isolated QA: content decision, fixture only.");
  await detail
    .getByRole("button", { name: "Duyệt nội dung", exact: true })
    .click();
  await expect(detail.getByText(/Version thao tác: 4/)).toBeVisible();
  await expect(detail.locator(".badges")).toContainText("Nội dung đã duyệt");
  await page.getByLabel("Trạng thái phân loại").selectOption("classified");
  await expect(page.locator(".chunk-link")).toHaveCount(before.total + 1);
  await page.locator(".chunk-list article.selected input").check();
  await page
    .getByLabel("Version release", { exact: true })
    .fill("qa-browser-" + testInfo.project.name);
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Xuất manifest", exact: true })
    .click();
  const file = await downloaded;
  await file.saveAs(testInfo.outputPath("release.json"));
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Biên soạn tài liệu YHDP" }),
  ).toBeVisible();
  await page.getByLabel("Trạng thái phân loại").selectOption("classified");
  await expect(page.locator(".chunk-link")).toHaveCount(before.total + 1);
  await page.locator(".chunk-link").last().click();
  await expect(
    detail.getByRole("heading", { name: "Lịch sử quyết định" }),
  ).toBeVisible();
  await expect(detail.locator(".decision")).toHaveCount(2);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth + 1,
    ),
  ).toBe(false);
  await page.screenshot({
    path: testInfo.outputPath("content-reviewer.png"),
    fullPage: false,
  });
  expect(errors).toEqual([]);
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await expect(
    page.getByRole("heading", { name: "Kho tài liệu", exact: true }),
  ).toBeVisible();
});
