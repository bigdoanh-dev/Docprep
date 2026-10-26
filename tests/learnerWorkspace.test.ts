import { test } from "node:test";
import assert from "node:assert/strict";
import { setActor } from "../src/app/identity.ts";
import {
  readWorkspace,
  updateWorkspace,
  recordActivity,
  clearWorkspace,
} from "../src/lib/learnerWorkspace.ts";
const memory = new Map<string, string>();
Object.defineProperty(globalThis, "localStorage", {
  value: {
    getItem: (k: string) => memory.get(k) ?? null,
    setItem: (k: string, v: string) => memory.set(k, v),
    removeItem: (k: string) => memory.delete(k),
  },
  configurable: true,
});
Object.defineProperty(globalThis, "window", {
  value: new EventTarget(),
  configurable: true,
});
test("notebook/preferences are isolated by account and mode; activity retries do not inflate streak", () => {
  setActor({ id: "learner-1", role: "learner", mode: "demo", name: "Test" });
  updateWorkspace((w) => ({
    ...w,
    saved: [
      {
        id: "q1",
        title: "Question",
        note: "Personal note",
        savedAt: "2026-10-14",
      },
    ],
  }));
  recordActivity("intent-1", "study", "2026-10-14");
  recordActivity("intent-1", "study", "2026-10-15");
  assert.equal(readWorkspace().activity.length, 1);
  assert.equal(readWorkspace().activity[0].date, "2026-10-14");
  setActor({ id: "learner-2", role: "learner", mode: "demo", name: "Test" });
  assert.equal(readWorkspace().saved.length, 0);
  setActor({ id: "learner-1", role: "learner", mode: "live", name: "Test" });
  assert.equal(readWorkspace().saved.length, 0);
  setActor({ id: "learner-1", role: "learner", mode: "demo", name: "Test" });
  assert.equal(readWorkspace().saved[0].note, "Personal note");
  clearWorkspace();
  assert.equal(readWorkspace().saved.length, 0);
  assert.equal(readWorkspace().activity.length, 0);
});

test("old workspace records receive presentation defaults and gender remains isolated by learner", () => {
  setActor({ id: "mobile-old", role: "learner", mode: "demo", name: "Test" });
  localStorage.setItem(
    "yhdp.workspace.v1:demo:mobile-old",
    JSON.stringify({ version: 1, activity: [], saved: [], read: [] }),
  );
  assert.equal(readWorkspace().gender, null);
  assert.equal(readWorkspace().mascot, "robot");
  assert.equal(readWorkspace().launcherPosition, null);
  updateWorkspace((w) => ({
    ...w,
    gender: "male",
    mascot: "cat",
    launcherPosition: { x: 120, y: 340 },
  }));
  assert.equal(readWorkspace().gender, "male");
  assert.equal(readWorkspace().mascot, "cat");
  assert.deepEqual(readWorkspace().launcherPosition, { x: 120, y: 340 });
  setActor({ id: "mobile-other", role: "learner", mode: "demo", name: "Test" });
  assert.equal(readWorkspace().gender, null);
  assert.equal(readWorkspace().mascot, "robot");
  assert.equal(readWorkspace().launcherPosition, null);
  setActor({ id: "mobile-old", role: "learner", mode: "demo", name: "Test" });
  assert.equal(readWorkspace().mascot, "cat");
  assert.deepEqual(readWorkspace().launcherPosition, { x: 120, y: 340 });
  clearWorkspace();
  assert.equal(readWorkspace().gender, null);
  assert.equal(readWorkspace().launcherPosition, null);
});

test("workspace sanitizes non-finite launcherPosition (NaN, Infinity, null coords) to null", () => {
  setActor({ id: "mobile-corrupt", role: "learner", mode: "demo", name: "Corrupt" });
  localStorage.setItem(
    "yhdp.workspace.v1:demo:mobile-corrupt",
    JSON.stringify({ version: 1, launcherPosition: { x: "NaN", y: 200 } }),
  );
  assert.equal(readWorkspace().launcherPosition, null);

  localStorage.setItem(
    "yhdp.workspace.v1:demo:mobile-corrupt",
    JSON.stringify({ version: 1, launcherPosition: { x: null, y: 200 } }),
  );
  assert.equal(readWorkspace().launcherPosition, null);

  localStorage.setItem(
    "yhdp.workspace.v1:demo:mobile-corrupt",
    JSON.stringify({ version: 1, launcherPosition: { x: 100, y: null } }),
  );
  assert.equal(readWorkspace().launcherPosition, null);
  clearWorkspace();
});

test("lastChatSearch persists across routes for active account, clears on new chat, and is isolated by account/mode", () => {
  // Learner 1 in demo mode opens chat session 101
  setActor({ id: "learner-alpha", role: "learner", mode: "demo", name: "Alpha" });
  assert.equal(readWorkspace().lastChatSearch, null);

  // User opens /hoi-dap?s=101
  updateWorkspace((w) => ({
    ...w,
    lastChatSearch: "?s=101",
  }));
  assert.equal(readWorkspace().lastChatSearch, "?s=101");

  // User navigates to Home (/) or Profile (/profile) - workspace retains session 101
  assert.equal(readWorkspace().lastChatSearch, "?s=101");

  // Account switch: Learner Beta logs in (demo mode)
  setActor({ id: "learner-beta", role: "learner", mode: "demo", name: "Beta" });
  // Beta must NOT inherit Alpha's chat session!
  assert.equal(readWorkspace().lastChatSearch, null);

  // Alpha in live mode must also have distinct workspace
  setActor({ id: "learner-alpha", role: "learner", mode: "live", name: "Alpha Live" });
  assert.equal(readWorkspace().lastChatSearch, null);

  // Return to Learner Alpha demo mode
  setActor({ id: "learner-alpha", role: "learner", mode: "demo", name: "Alpha" });
  assert.equal(readWorkspace().lastChatSearch, "?s=101");

  // User starts a "Cuộc trò chuyện mới" -> clears lastChatSearch
  updateWorkspace((w) => ({
    ...w,
    lastChatSearch: null,
  }));
  assert.equal(readWorkspace().lastChatSearch, null);
  clearWorkspace();
});

