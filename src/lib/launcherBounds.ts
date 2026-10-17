export type Point = {
  x: number;
  y: number;
};

export type LauncherSize = {
  width: number;
  height: number;
};

export type ContainerRect = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

export type VisualViewportState = {
  offsetLeft: number;
  offsetTop: number;
  width: number;
  height: number;
};

export type ElementRect = {
  left: number;
  right: number;
  top: number;
  bottom: number;
};

export type ClampBoundsOptions = {
  containerRect: ContainerRect;
  footerRects?: Array<{ top: number; height?: number }>;
  headerRect?: { bottom: number };
  launcherSize?: LauncherSize;
  margin?: number;
};

export const DEFAULT_LAUNCHER_SIZE: LauncherSize = {
  width: 49,
  height: 54,
};

export const DEFAULT_MARGIN = 8;
export const DRAG_THRESHOLD = 6;

/**
 * Validates that a value is a finite number (not NaN, Infinity, -Infinity).
 */
export function isValidCoordinate(val: unknown): val is number {
  return typeof val === "number" && Number.isFinite(val);
}

/**
 * Validates that an object has finite numerical x and y coordinates.
 */
export function isValidPoint(p: unknown): p is Point {
  return (
    typeof p === "object" &&
    p !== null &&
    isValidCoordinate((p as Point).x) &&
    isValidCoordinate((p as Point).y)
  );
}

/**
 * Computes the visible intersection rectangle between the app container and the visual viewport.
 * Accounts for visualViewport.offsetTop (keyboard / vertical pan),
 * visualViewport.offsetLeft (horizontal zoom / pan), and bounds the visible workspace
 * so fixed elements stay within both the mobile app container and the user's visible screen.
 */
export function intersectAppWithVisualViewport(
  appRect?: ElementRect | null,
  vv?: VisualViewportState | null,
  layoutViewport: { width: number; height: number } = { width: 390, height: 844 },
): ContainerRect {
  const vvLeft = vv ? vv.offsetLeft : 0;
  const vvTop = vv ? vv.offsetTop : 0;
  const vvWidth = vv ? vv.width : layoutViewport.width;
  const vvHeight = vv ? vv.height : layoutViewport.height;
  const vvRight = vvLeft + vvWidth;
  const vvBottom = vvTop + vvHeight;

  const appLeft = appRect ? appRect.left : vvLeft;
  const appRight = appRect ? appRect.right : vvRight;
  const appTop = appRect ? appRect.top : vvTop;
  const appBottom = appRect ? appRect.bottom : vvBottom;

  // Intersect app container with visible visual viewport
  const left = appRect ? Math.max(vvLeft, appLeft) : vvLeft;
  const right = appRect ? Math.min(vvRight, appRight) : vvRight;
  const top = appRect ? Math.max(vvTop, appTop) : vvTop;
  const bottom = appRect ? Math.min(vvBottom, appBottom) : vvBottom;

  return {
    left,
    right: Math.max(left, right),
    top,
    bottom: Math.max(top, bottom),
  };
}

/**
 * Calculates valid coordinate boundaries for the launcher.
 * - Allows dragging anywhere within the visible app frame (including top/header area).
 * - Strictly prevents any overlap with footers or bottom input bars.
 * - Prioritizes visible area and footer clearance on short screens / virtual keyboards.
 */
export function calculateLauncherBoundaries(options: ClampBoundsOptions) {
  const {
    containerRect,
    footerRects = [],
    launcherSize = DEFAULT_LAUNCHER_SIZE,
    margin = DEFAULT_MARGIN,
  } = options;

  const width = launcherSize.width || DEFAULT_LAUNCHER_SIZE.width;
  const height = launcherSize.height || DEFAULT_LAUNCHER_SIZE.height;

  // Horizontal bounds: strictly inside the app container
  let minX = containerRect.left + margin;
  let maxX = containerRect.right - width - margin;
  if (maxX < minX) {
    minX = containerRect.left;
    maxX = containerRect.left;
  }

  // Bottom bound: must never overlap any footer element (strict top priority)
  let lowestAllowedBottom = containerRect.bottom - margin;
  for (const f of footerRects) {
    if (typeof f.top === "number" && Number.isFinite(f.top) && f.top > 0) {
      lowestAllowedBottom = Math.min(lowestAllowedBottom, f.top - margin);
    }
  }

  // Maximum Y allowed so launcher bottom never exceeds lowestAllowedBottom
  const maxY = lowestAllowedBottom - height;

  // Top bound: user can place launcher anywhere in the visible app frame (including top / header)
  let minY = containerRect.top + margin;

  // In low screens or with virtual keyboard open, never allow minY to push launcher into footer
  if (minY > maxY) {
    minY = maxY;
  }

  return {
    minX,
    maxX,
    minY,
    maxY,
    width,
    height,
  };
}

/**
 * Clamps any given coordinate into the strictly valid bounds.
 * Falls back to default position if pos contains non-finite numbers (NaN, Infinity, etc.).
 */
export function clampLauncherPosition(
  pos: unknown,
  options: ClampBoundsOptions,
): Point {
  const { minX, maxX, minY, maxY } = calculateLauncherBoundaries(options);
  if (!isValidPoint(pos)) {
    return getDefaultLauncherPosition(options);
  }
  const clampedX = Math.round(Math.max(minX, Math.min(maxX, pos.x)));
  const clampedY = Math.round(Math.max(minY, Math.min(maxY, pos.y)));
  return { x: clampedX, y: clampedY };
}

/**
 * Snaps a launcher coordinate to the nearest allowed edge: LEFT, RIGHT, or TOP.
 * The launcher is NOT allowed to stick in the middle of the screen or to the bottom (footer edge).
 * Always clamps to valid container bounds and footer clearance first.
 */
export function snapLauncherToEdge(
  pos: unknown,
  options: ClampBoundsOptions,
): Point {
  const { minX, maxX, minY, maxY } = calculateLauncherBoundaries(options);
  if (!isValidPoint(pos)) {
    return getDefaultLauncherPosition(options);
  }

  // 1. Clamp into valid boundaries
  const cx = Math.round(Math.max(minX, Math.min(maxX, pos.x)));
  const cy = Math.round(Math.max(minY, Math.min(maxY, pos.y)));

  // 2. Measure distance to the 3 allowed edges (LEFT, RIGHT, TOP - NO BOTTOM EDGE)
  const distLeft = Math.abs(cx - minX);
  const distRight = Math.abs(maxX - cx);
  const distTop = Math.abs(cy - minY);

  // 3. Snap to the nearest edge among LEFT, RIGHT, TOP
  if (distLeft <= distRight && distLeft <= distTop) {
    // Snap to LEFT edge, keeping vertical position
    return { x: minX, y: cy };
  } else if (distRight <= distTop) {
    // Snap to RIGHT edge, keeping vertical position
    return { x: maxX, y: cy };
  } else {
    // Snap to TOP edge, keeping horizontal position
    return { x: cx, y: minY };
  }
}

/**
 * Computes the default resting position (bottom-right, above footer).
 */
export function getDefaultLauncherPosition(
  options: ClampBoundsOptions,
): Point {
  const { maxX, maxY } = calculateLauncherBoundaries(options);
  return {
    x: Math.round(maxX),
    y: Math.round(maxY),
  };
}

/**
 * Measures live DOM geometry for bounds clamping in the browser.
 * Intersects the mobile app frame with visualViewport (handling keyboard offsetTop/height).
 */
export function measureCurrentBounds(customLauncherSize?: LauncherSize): ClampBoundsOptions {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return {
      containerRect: { left: 0, right: 390, top: 0, bottom: 844 },
      launcherSize: customLauncherSize ?? DEFAULT_LAUNCHER_SIZE,
    };
  }

  const appEl = document.querySelector(".mobile-app");
  const appRect = appEl?.getBoundingClientRect();

  const vv = window.visualViewport;
  const vvState: VisualViewportState | undefined = vv
    ? {
        offsetLeft: vv.offsetLeft,
        offsetTop: vv.offsetTop,
        width: vv.width,
        height: vv.height,
      }
    : undefined;

  const containerRect = intersectAppWithVisualViewport(
    appRect
      ? {
          left: appRect.left,
          right: appRect.right,
          top: appRect.top,
          bottom: appRect.bottom,
        }
      : undefined,
    vvState,
    { width: window.innerWidth, height: window.innerHeight },
  );

  const headerEl = document.querySelector(".mobile-header");
  const headerRect = headerEl?.getBoundingClientRect();

  // Find footers: main navigation footer, and chat conversation input footer if present
  const footerSelectors = [".mobile-footer", ".conversation-panel > .footer"];
  const footerRects: Array<{ top: number; height?: number }> = [];

  for (const sel of footerSelectors) {
    const el = document.querySelector(sel);
    if (el) {
      const r = el.getBoundingClientRect();
      if (r.top > 0 && r.height > 0) {
        footerRects.push({ top: r.top, height: r.height });
      }
    }
  }

  return {
    containerRect,
    headerRect: headerRect ? { bottom: headerRect.bottom } : undefined,
    footerRects,
    launcherSize: customLauncherSize ?? DEFAULT_LAUNCHER_SIZE,
  };
}
