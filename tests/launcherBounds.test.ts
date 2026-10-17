import { test } from "node:test";
import assert from "node:assert/strict";
import {
  calculateLauncherBoundaries,
  clampLauncherPosition,
  getDefaultLauncherPosition,
  intersectAppWithVisualViewport,
  isValidCoordinate,
  isValidPoint,
  snapLauncherToEdge,
  DEFAULT_LAUNCHER_SIZE,
  DEFAULT_MARGIN,
  DRAG_THRESHOLD,
} from "../src/lib/launcherBounds.ts";

test("launcher boundaries stay strictly inside 320px mobile viewport", () => {
  const options = {
    containerRect: { left: 0, right: 320, top: 0, bottom: 568 },
    footerRects: [{ top: 500, height: 68 }],
    launcherSize: { width: 49, height: 54 },
    margin: DEFAULT_MARGIN,
  };

  const bounds = calculateLauncherBoundaries(options);
  assert.equal(bounds.minX, 8);
  assert.equal(bounds.maxX, 320 - 49 - 8); // 263
  assert.equal(bounds.minY, 8); // top margin, user allowed in upper area
  assert.equal(bounds.maxY, 500 - 8 - 54); // 438

  // Clamp left overrun
  const farLeft = clampLauncherPosition({ x: -50, y: 200 }, options);
  assert.equal(farLeft.x, 8);

  // Clamp right overrun
  const farRight = clampLauncherPosition({ x: 400, y: 200 }, options);
  assert.equal(farRight.x, 263);

  // Verify launcher right edge never exceeds screen width
  assert.ok(farRight.x + 49 <= 320);
});

test("dragging up to top corner (0, 0) allows placing over top area without header blockage", () => {
  const options = {
    containerRect: { left: 0, right: 390, top: 0, bottom: 844 },
    footerRects: [{ top: 760, height: 84 }],
    headerRect: { bottom: 124 },
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };

  const bounds = calculateLauncherBoundaries(options);
  assert.equal(bounds.minY, 8); // allows top area, not blocked by header bottom

  // Dragging to top-left corner (0, 0)
  const topLeft = clampLauncherPosition({ x: 0, y: 0 }, options);
  assert.equal(topLeft.x, 8);
  assert.equal(topLeft.y, 8);

  // Dragging to top-right corner (390, 0)
  const topRight = clampLauncherPosition({ x: 390, y: 0 }, options);
  assert.equal(topRight.x, 390 - 49 - 8); // 333
  assert.equal(topRight.y, 8);
});

test("low screen / virtual keyboard: container 390x180, header bottom=124, footer top=130 clamps y <= 68 and never overlaps footer", () => {
  // Codex specific test case
  const options = {
    containerRect: { left: 0, right: 390, top: 0, bottom: 180 },
    footerRects: [{ top: 130, height: 50 }],
    headerRect: { bottom: 124 },
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };

  const bounds = calculateLauncherBoundaries(options);
  assert.ok(
    bounds.maxY <= 68,
    `maxY (${bounds.maxY}) must be <= 68 to never collide with footer at 130`,
  );
  assert.equal(bounds.maxY, 68); // 130 - 8 - 54 = 68
  assert.equal(bounds.minY, 8);

  // Position at y=150 (near or inside footer) must clamp to <= 68, never 132
  const clamped = clampLauncherPosition({ x: 200, y: 150 }, options);
  assert.equal(clamped.y, 68);
  assert.notEqual(clamped.y, 132);

  // Verify launcher bottom is strictly above footer top
  const launcherBottom = clamped.y + 54;
  assert.ok(launcherBottom < 130, `Launcher bottom (${launcherBottom}) must be strictly < footer top (130)`);
  assert.equal(130 - launcherBottom, 8);
});

test("clamping after resize from desktop to narrow mobile viewport", () => {
  // Desktop configuration (1280px screen, centered 480px app: left 400, right 880)
  const desktopOptions = {
    containerRect: { left: 400, right: 880, top: 0, bottom: 900 },
    footerRects: [{ top: 820, height: 80 }],
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };

  const desktopPos = clampLauncherPosition({ x: 800, y: 700 }, desktopOptions);
  assert.equal(desktopPos.x, 800);
  assert.equal(desktopPos.y, 700);

  // Window resized to mobile 320x568 (footer at top 500)
  const mobileOptions = {
    containerRect: { left: 0, right: 320, top: 0, bottom: 568 },
    footerRects: [{ top: 500, height: 68 }],
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };

  // Re-clamping previously saved desktop position into mobile bounds
  const resizedPos = clampLauncherPosition(desktopPos, mobileOptions);
  assert.equal(resizedPos.x, 320 - 49 - 8); // 263
  assert.equal(resizedPos.y, 500 - 8 - 54); // 438
  assert.ok(resizedPos.x + 49 <= 320);
  assert.ok(resizedPos.y + 54 < 500);
});

test("validates finite coordinates: NaN, Infinity, null, and non-numbers safely fallback to default position", () => {
  const options = {
    containerRect: { left: 0, right: 390, top: 0, bottom: 844 },
    footerRects: [{ top: 760, height: 84 }],
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };

  const expectedDefault = getDefaultLauncherPosition(options);
  assert.equal(expectedDefault.x, 333);
  assert.equal(expectedDefault.y, 698);

  // Validate helper functions
  assert.equal(isValidCoordinate(100), true);
  assert.equal(isValidCoordinate(0), true);
  assert.equal(isValidCoordinate(-5), true);
  assert.equal(isValidCoordinate(NaN), false);
  assert.equal(isValidCoordinate(Infinity), false);
  assert.equal(isValidCoordinate(-Infinity), false);
  assert.equal(isValidCoordinate("100"), false);
  assert.equal(isValidCoordinate(null), false);

  assert.equal(isValidPoint({ x: 100, y: 200 }), true);
  assert.equal(isValidPoint({ x: NaN, y: 200 }), false);
  assert.equal(isValidPoint({ x: 100, y: Infinity }), false);
  assert.equal(isValidPoint(null), false);
  assert.equal(isValidPoint(undefined), false);
  assert.equal(isValidPoint({ x: "100", y: 200 }), false);

  // Corrupted / legacy inputs should safely resolve to default position
  assert.deepEqual(clampLauncherPosition({ x: NaN, y: 100 }, options), expectedDefault);
  assert.deepEqual(clampLauncherPosition({ x: Infinity, y: -Infinity }, options), expectedDefault);
  assert.deepEqual(clampLauncherPosition(null, options), expectedDefault);
  assert.deepEqual(clampLauncherPosition(undefined, options), expectedDefault);
  assert.deepEqual(clampLauncherPosition("corrupted", options), expectedDefault);
  assert.deepEqual(clampLauncherPosition({ x: 100 }, options), expectedDefault);
});

test("launcher boundaries strictly confined within 480px mobile frame on desktop", () => {
  const options = {
    containerRect: { left: 400, right: 880, top: 0, bottom: 900 },
    footerRects: [{ top: 820, height: 80 }],
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };

  const bounds = calculateLauncherBoundaries(options);
  assert.equal(bounds.minX, 408);
  assert.equal(bounds.maxX, 880 - 49 - 8); // 823
  assert.equal(bounds.maxY, 820 - 8 - 54); // 758

  // Attempt to drag out to the left side of desktop screen
  const desktopLeft = clampLauncherPosition({ x: 50, y: 300 }, options);
  assert.equal(desktopLeft.x, 408);

  // Attempt to drag out to the right side of desktop screen
  const desktopRight = clampLauncherPosition({ x: 1200, y: 300 }, options);
  assert.equal(desktopRight.x, 823);

  // Verify right edge stays within app boundary
  assert.ok(desktopRight.x + 49 <= 880);
});

test("strict footer avoidance: launcher never overlaps or intersects footer", () => {
  const footerTop = 720;
  const launcherHeight = 54;
  const margin = 8;

  const options = {
    containerRect: { left: 0, right: 390, top: 0, bottom: 844 },
    footerRects: [{ top: footerTop, height: 74 }],
    launcherSize: { width: 49, height: launcherHeight },
    margin,
  };

  // Dragging directly into footer area
  const draggedIntoFooter = clampLauncherPosition({ x: 300, y: 780 }, options);
  assert.equal(draggedIntoFooter.y, footerTop - margin - launcherHeight); // 658

  const launcherBottom = draggedIntoFooter.y + launcherHeight;
  assert.ok(
    launcherBottom < footerTop,
    `Launcher bottom (${launcherBottom}) must be strictly less than footer top (${footerTop})`,
  );
  assert.equal(footerTop - launcherBottom, margin);
});

test("multiple footer obstacles: avoids both chat input bar and navigation footer", () => {
  const options = {
    containerRect: { left: 0, right: 390, top: 0, bottom: 844 },
    footerRects: [
      { top: 760, height: 84 }, // .mobile-footer
      { top: 680, height: 60 }, // .conversation-panel > .footer (chat input bar)
    ],
    launcherSize: DEFAULT_LAUNCHER_SIZE,
    margin: 8,
  };

  const bounds = calculateLauncherBoundaries(options);
  // Must avoid the higher footer (680)
  assert.equal(bounds.maxY, 680 - 8 - 54); // 618

  const pos = clampLauncherPosition({ x: 300, y: 700 }, options);
  assert.equal(pos.y, 618);
  assert.ok(pos.y + 54 <= 680 - 8);
});

test("default launcher position sits at bottom-right above footer", () => {
  const options = {
    containerRect: { left: 0, right: 390, top: 0, bottom: 844 },
    footerRects: [{ top: 760, height: 84 }],
    launcherSize: DEFAULT_LAUNCHER_SIZE,
    margin: 8,
  };

  const def = getDefaultLauncherPosition(options);
  assert.equal(def.x, 390 - 49 - 8); // 333
  assert.equal(def.y, 760 - 8 - 54); // 698
  assert.ok(def.x > 0);
  assert.ok(def.y > 0);
  assert.ok(def.y + 54 < 760);
});

test("drag threshold distinguishes tap (< 6px) vs drag (>= 6px)", () => {
  assert.equal(DRAG_THRESHOLD, 6);

  const isDrag = (dx: number, dy: number) => Math.hypot(dx, dy) >= DRAG_THRESHOLD;

  // Small pointer jitter during tap
  assert.equal(isDrag(1, 2), false);
  assert.equal(isDrag(3, 3), false);
  assert.equal(isDrag(4, 3), false); // hypot = 5 < 6

  // Intentional drag movement
  assert.equal(isDrag(6, 0), true);
  assert.equal(isDrag(0, 6), true);
  assert.equal(isDrag(5, 5), true); // hypot ≈ 7.07 >= 6
  assert.equal(isDrag(20, 30), true);
});

test("intersectAppWithVisualViewport correctly bounds visible area under virtual keyboard and pan offsets", () => {
  // Scenario 1: Mobile with virtual keyboard open
  // Screen layout 390x844; keyboard reduces height to 360 and scrolls down with offsetTop 120
  const mobileKeyboardVV = {
    offsetLeft: 0,
    offsetTop: 120,
    width: 390,
    height: 360,
  };
  const mobileAppRect = {
    left: 0,
    right: 390,
    top: -120, // Page scrolled up by 120px
    bottom: 1200,
  };

  const containerRect = intersectAppWithVisualViewport(
    mobileAppRect,
    mobileKeyboardVV,
    { width: 390, height: 844 },
  );

  assert.equal(containerRect.left, 0);
  assert.equal(containerRect.right, 390);
  assert.equal(containerRect.top, 120); // strictly bounds top to visible offsetTop
  assert.equal(containerRect.bottom, 120 + 360); // 480, strictly above keyboard

  // Verify launcher bounds in this keyboard view
  const bounds = calculateLauncherBoundaries({
    containerRect,
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  });

  // Launcher minY must be within the visible visual viewport, never hidden behind the top offset
  assert.equal(bounds.minY, 120 + 8); // 128
  assert.equal(bounds.maxY, 480 - 8 - 54); // 418

  // Position at y=50 (which would be cut off by the top offset) is clamped into view at 128
  const clampedCutOff = clampLauncherPosition({ x: 200, y: 50 }, { containerRect });
  assert.equal(clampedCutOff.y, 128);

  // Position at y=600 (hidden behind keyboard) is clamped into view at 418
  const clampedKeyboard = clampLauncherPosition({ x: 200, y: 600 }, { containerRect });
  assert.equal(clampedKeyboard.y, 418);
});

test("intersectAppWithVisualViewport handles desktop centered app and horizontal pan offsets", () => {
  // Scenario 2: Desktop 1280px with centered 480px app, horizontal zoom offsetLeft: 30
  const desktopZoomVV = {
    offsetLeft: 30,
    offsetTop: 0,
    width: 1200,
    height: 900,
  };
  const desktopAppRect = {
    left: 400,
    right: 880,
    top: 0,
    bottom: 900,
  };

  const containerRect = intersectAppWithVisualViewport(
    desktopAppRect,
    desktopZoomVV,
    { width: 1280, height: 900 },
  );

  // Intersects [30, 1230] with [400, 880] -> [400, 880]
  assert.equal(containerRect.left, 400);
  assert.equal(containerRect.right, 880);
  assert.equal(containerRect.top, 0);
  assert.equal(containerRect.bottom, 900);

  // If zoomed into app (offsetLeft: 450, width: 400)
  const zoomedVV = {
    offsetLeft: 450,
    offsetTop: 0,
    width: 400,
    height: 900,
  };
  const zoomedContainer = intersectAppWithVisualViewport(
    desktopAppRect,
    zoomedVV,
    { width: 1280, height: 900 },
  );
  assert.equal(zoomedContainer.left, 450);
  assert.equal(zoomedContainer.right, 850);
});

test("desktop 1280px with appRect.top = 20 clamps launcher top to y=28 (never y=8), preventing top overflow", () => {
  const desktopAppRect = {
    left: 400,
    right: 880,
    top: 20, // margin-top: 20px on desktop
    bottom: 880,
  };
  const desktopVV = {
    offsetLeft: 0,
    offsetTop: 0,
    width: 1280,
    height: 900,
  };

  const containerRect = intersectAppWithVisualViewport(
    desktopAppRect,
    desktopVV,
    { width: 1280, height: 900 },
  );

  assert.equal(containerRect.top, 20); // must be 20, not 0!
  assert.equal(containerRect.bottom, 880);

  const bounds = calculateLauncherBoundaries({
    containerRect,
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  });

  // minY must be 20 + 8 = 28, never 8
  assert.equal(bounds.minY, 28);

  // Dragging to top-left corner of screen (x: 400, y: 0)
  const clamped = clampLauncherPosition({ x: 400, y: 0 }, { containerRect });
  assert.equal(clamped.y, 28);
  assert.notEqual(clamped.y, 8);
  assert.ok(clamped.y >= 20, "Launcher must stay inside desktop app frame (y >= 20)");
});

test("snapLauncherToEdge: snaps middle-left to LEFT edge, middle-right to RIGHT edge, and upper-center to TOP edge", () => {
  // Mobile 390x844 with footer top at 760
  const options = {
    containerRect: { left: 0, right: 390, top: 0, bottom: 844 },
    footerRects: [{ top: 760, height: 84 }],
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };
  const bounds = calculateLauncherBoundaries(options);
  assert.equal(bounds.minX, 8);
  assert.equal(bounds.maxX, 333);
  assert.equal(bounds.minY, 8);
  assert.equal(bounds.maxY, 698);

  // 1. Middle-left position (x: 80, y: 400) -> distance to left (72) is much less than right (253) or top (392)
  const snappedLeft = snapLauncherToEdge({ x: 80, y: 400 }, options);
  assert.equal(snappedLeft.x, 8, "Must snap to LEFT edge (x=8)");
  assert.equal(snappedLeft.y, 400, "Must preserve vertical position (y=400)");

  // 2. Middle-right position (x: 290, y: 400) -> distance to right (43) is much less than left (282) or top (392)
  const snappedRight = snapLauncherToEdge({ x: 290, y: 400 }, options);
  assert.equal(snappedRight.x, 333, "Must snap to RIGHT edge (x=333)");
  assert.equal(snappedRight.y, 400, "Must preserve vertical position (y=400)");

  // 3. Upper-center position (x: 180, y: 30) -> distance to top (22) is much less than left (172) or right (153)
  const snappedTop = snapLauncherToEdge({ x: 180, y: 30 }, options);
  assert.equal(snappedTop.x, 180, "Must preserve horizontal position (x=180)");
  assert.equal(snappedTop.y, 8, "Must snap to TOP edge (y=8)");
});

test("snapLauncherToEdge: NEVER snaps to bottom edge (no bottom edge), snaps to LEFT or RIGHT edge and respects footer", () => {
  const options = {
    containerRect: { left: 0, right: 390, top: 0, bottom: 844 },
    footerRects: [{ top: 760, height: 84 }],
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };
  const bounds = calculateLauncherBoundaries(options);
  assert.equal(bounds.maxY, 698); // 760 - 8 - 54

  // Lower-center position near footer (x: 195, y: 690)
  // Distance to top = 690 - 8 = 682
  // Distance to left = 195 - 8 = 187
  // Distance to right = 333 - 195 = 138
  // Nearest edge is RIGHT! It must NOT snap to bottom edge across the center!
  const lowerCenter = snapLauncherToEdge({ x: 195, y: 690 }, options);
  assert.equal(lowerCenter.x, 333, "Must snap to RIGHT edge (x=333)");
  assert.equal(lowerCenter.y, 690, "Must keep y=690 above footer, never overlap footer");

  // Bottom clearance verified:
  const bottomEdge = lowerCenter.y + 54;
  assert.ok(bottomEdge <= 760 - 8, `Launcher bottom (${bottomEdge}) must be <= footerTop - margin (${760 - 8})`);

  // Lower-left position near footer (x: 100, y: 695)
  const lowerLeft = snapLauncherToEdge({ x: 100, y: 695 }, options);
  assert.equal(lowerLeft.x, 8, "Must snap to LEFT edge (x=8)");
  assert.equal(lowerLeft.y, 695, "Must keep y=695 above footer");
});

test("snapLauncherToEdge: migrates saved center position to nearest edge and handles 320px/desktop", () => {
  // Mobile 390: A legacy saved position in the dead center (x: 170, y: 400)
  const options390 = {
    containerRect: { left: 0, right: 390, top: 0, bottom: 844 },
    footerRects: [{ top: 760, height: 84 }],
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };
  const migratedCenter = snapLauncherToEdge({ x: 170, y: 400 }, options390);
  assert.equal(migratedCenter.x, 8, "Center-left legacy position snaps to LEFT edge");
  assert.equal(migratedCenter.y, 400);

  // 320px viewport: container 320x568, footer 500
  const options320 = {
    containerRect: { left: 0, right: 320, top: 0, bottom: 568 },
    footerRects: [{ top: 500, height: 68 }],
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };
  // Snapping in 320px screen: bounds minX=8, maxX=263
  const snap320Right = snapLauncherToEdge({ x: 200, y: 300 }, options320);
  assert.equal(snap320Right.x, 263);
  assert.equal(snap320Right.y, 300);

  // Desktop 1280px with centered 480px app frame (left 400, right 880, top 20)
  const desktopOptions = {
    containerRect: { left: 400, right: 880, top: 20, bottom: 880 },
    footerRects: [{ top: 800, height: 80 }],
    launcherSize: { width: 49, height: 54 },
    margin: 8,
  };
  // Left side of desktop frame
  const desktopLeft = snapLauncherToEdge({ x: 500, y: 400 }, desktopOptions);
  assert.equal(desktopLeft.x, 408, "Snaps to LEFT edge of 480px desktop container (408)");

  // Upper side of desktop frame
  const desktopUpper = snapLauncherToEdge({ x: 640, y: 40 }, desktopOptions);
  assert.equal(desktopUpper.y, 28, "Snaps to TOP edge of desktop container with margin (28)");
  assert.equal(desktopUpper.x, 640);
});



