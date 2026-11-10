import { execFileSync } from "node:child_process";
import path from "node:path";

/** Test-only provisioning: keep generated credentials in memory, out of the test log. */
export function passwordAccount(): { username: string; password: string } {
  const output = process.env.PHASE1_URL
    ? execFileSync(
        "docker",
        [
          "compose",
          "--env-file",
          ".env.phase1",
          "-f",
          "deploy/compose.phase1.yml",
          "run",
          "--rm",
          "--no-deps",
          "seed",
          "python",
          "-m",
          "seed.browser",
          "--password-account",
        ],
        { cwd: process.cwd(), encoding: "utf8" },
      )
    : execFileSync(
        path.join(
          process.cwd(),
          "backend",
          ".venv",
          process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
        ),
        ["-m", "seed.browser", "--password-account"],
        {
          cwd: path.join(process.cwd(), "backend"),
          encoding: "utf8",
        },
      );
  return JSON.parse(output);
}
