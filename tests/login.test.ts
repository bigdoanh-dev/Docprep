import test from "node:test";
import assert from "node:assert/strict";
import { usernameLogin } from "../src/lib/login";

const tokenPair = {
  access_token: "test-access-token",
  refresh_token: "test-refresh-token",
  expires_in: 1800,
  role: "ministry_viewer",
  consent_required: false,
};

test("password sign-in keeps the Phase 1 endpoint, token pair and server role", async () => {
  const result = await usernameLogin(
    " user ",
    " secret ",
    async (url, init) => {
      assert.equal(url, "/api/v1/auth/staff/login");
      assert.equal(init?.method, "POST");
      assert.deepEqual(JSON.parse(String(init?.body)), {
        email: "user",
        password: " secret ",
      });
      assert.equal(new Headers(init?.headers).has("Authorization"), false);
      return Response.json(tokenPair);
    },
  );
  assert.deepEqual(result, tokenPair);
});
for (const [status, message] of [
  [401, /Sai tên đăng nhập hoặc mật khẩu/],
  [429, /Thử quá nhiều lần/],
  [500, /Không thể đăng nhập/],
] as const) {
  test(`sign-in reports HTTP ${status} in Vietnamese`, async () => {
    await assert.rejects(
      usernameLogin("user", "secret", async () => new Response("", { status })),
      message,
    );
  });
}
test("network failures and malformed successes do not produce a valid session response", async () => {
  await assert.rejects(
    usernameLogin("user", "secret", async () => {
      throw new TypeError("offline");
    }),
    /Không kết nối được/,
  );
  for (const body of [
    null,
    {},
    { token: "", username: "user", role: "user" },
    { token: "legacy-token", username: "user", role: "reviewer" },
    { ...tokenPair, refresh_token: "" },
    { ...tokenPair, expires_in: 0 },
    { ...tokenPair, consent_required: null },
  ]) {
    await assert.rejects(
      usernameLogin("user", "secret", async () => Response.json(body)),
      /Phản hồi đăng nhập không hợp lệ/,
    );
  }
});
