import test from "node:test";
import assert from "node:assert/strict";
import { usernameLogin } from "../src/lib/login";

test("password sign-in matches the reference endpoint and preserves password whitespace", async () => {
  const result = await usernameLogin(
    " user ",
    " secret ",
    async (url, init) => {
      assert.equal(url, "/api/v1/auth/login");
      assert.equal(init?.method, "POST");
      assert.deepEqual(JSON.parse(String(init?.body)), {
        username: "user",
        password: " secret ",
      });
      assert.equal(new Headers(init?.headers).has("Authorization"), false);
      return Response.json({
        token: "test-token",
        username: "user",
        role: "reviewer",
      });
    },
  );
  assert.equal(result.token, "test-token");
  assert.equal(result.username, "user");
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
  ]) {
    await assert.rejects(
      usernameLogin("user", "secret", async () => Response.json(body)),
      /Phản hồi đăng nhập không hợp lệ/,
    );
  }
});
