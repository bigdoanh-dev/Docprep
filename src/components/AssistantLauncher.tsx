import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Mascot } from "page-mascot";
import { useActor } from "../app/identity";
import {
  clampLauncherPosition,
  DEFAULT_LAUNCHER_SIZE,
  DRAG_THRESHOLD,
  getDefaultLauncherPosition,
  isValidPoint,
  measureCurrentBounds,
  snapLauncherToEdge,
  type LauncherSize,
  type Point,
} from "../lib/launcherBounds";
import { updateWorkspace, useWorkspace } from "../lib/learnerWorkspace";

export type AssistantLauncherProps = {
  mascot: string;
  onOpenChat: () => void;
};

export function AssistantLauncher({ mascot, onOpenChat }: AssistantLauncherProps) {
  const w = useWorkspace();
  const actor = useActor();
  const loc = useLocation();
  const launcherRef = useRef<HTMLDivElement>(null);

  // Primitive dependencies to avoid object reference recreation loops from useWorkspace()
  const savedX = isValidPoint(w.launcherPosition) ? w.launcherPosition.x : null;
  const savedY = isValidPoint(w.launcherPosition) ? w.launcherPosition.y : null;
  const actorKey = actor ? `${actor.mode}:${actor.id}` : "";

  // Initialize position immediately from workspace or default bounds, snapped to edge
  const [pos, setPos] = useState<Point>(() => {
    const bounds = measureCurrentBounds(DEFAULT_LAUNCHER_SIZE);
    if (savedX !== null && savedY !== null) {
      return snapLauncherToEdge({ x: savedX, y: savedY }, bounds);
    }
    return getDefaultLauncherPosition(bounds);
  });

  const [isDragging, setIsDragging] = useState(false);
  const dragStateRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    initialX: number;
    initialY: number;
    dragged: boolean;
  } | null>(null);

  const justDraggedRef = useRef(false);
  const openTriggeredRef = useRef(false);
  const currentPosRef = useRef(pos);
  currentPosRef.current = pos;

  const getRealSize = (): LauncherSize => {
    if (launcherRef.current) {
      const rect = launcherRef.current.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        return { width: Math.round(rect.width), height: Math.round(rect.height) };
      }
    }
    return DEFAULT_LAUNCHER_SIZE;
  };

  const triggerOpenChat = () => {
    if (openTriggeredRef.current) return;
    openTriggeredRef.current = true;
    setTimeout(() => {
      openTriggeredRef.current = false;
    }, 300);
    onOpenChat();
  };

  // Re-clamp and snap position whenever geometry changes (resize, orientation, route, visual viewport)
  // Only updates state if coordinates actually change (returns prev if identical)
  const clampCurrentPosition = () => {
    if (dragStateRef.current) return;
    const size = getRealSize();
    const bounds = measureCurrentBounds(size);
    setPos((prev) => {
      const next = snapLauncherToEdge(prev, bounds);
      if (prev.x === next.x && prev.y === next.y) {
        return prev;
      }
      return next;
    });
  };

  useLayoutEffect(() => {
    clampCurrentPosition();
  }, [loc.pathname, loc.search]);

  useEffect(() => {
    const onResize = () => clampCurrentPosition();
    const onScroll = () => clampCurrentPosition();

    window.addEventListener("resize", onResize, { passive: true });
    window.addEventListener("orientationchange", onResize, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });

    const vv = window.visualViewport;
    if (vv) {
      vv.addEventListener("resize", onResize);
      vv.addEventListener("scroll", onScroll);
    }

    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
      window.removeEventListener("scroll", onScroll);
      if (vv) {
        vv.removeEventListener("resize", onResize);
        vv.removeEventListener("scroll", onScroll);
      }
    };
  }, []);

  // Sync when workspace position or account changes, using primitive dependencies
  // Bails out if target coordinates match current position to prevent render loops
  useEffect(() => {
    if (dragStateRef.current) return;
    const size = getRealSize();
    const bounds = measureCurrentBounds(size);
    const target =
      savedX !== null && savedY !== null
        ? { x: savedX, y: savedY }
        : null;
    const next = target
      ? snapLauncherToEdge(target, bounds)
      : getDefaultLauncherPosition(bounds);

    setPos((prev) => {
      if (prev.x === next.x && prev.y === next.y) {
        return prev;
      }
      return next;
    });
  }, [savedX, savedY, actorKey]);

  // Ensure the Mascot button has an accurate accessible name
  useEffect(() => {
    const btn = launcherRef.current?.querySelector("button");
    if (btn) {
      btn.setAttribute("aria-label", "Mở Gia sư AI");
    }
  }, [mascot]);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    // Only primary pointer (e.g. first touch / main mouse button)
    // Guard against secondary touches or simultaneous pointers hijacking active drag
    if (!e.isPrimary || e.button !== 0 || dragStateRef.current) return;

    const target = e.currentTarget;
    try {
      target.setPointerCapture(e.pointerId);
    } catch {}

    dragStateRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      initialX: currentPosRef.current.x,
      initialY: currentPosRef.current.y,
      dragged: false,
    };
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragStateRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;

    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    const dist = Math.hypot(dx, dy);

    if (!drag.dragged) {
      if (dist < DRAG_THRESHOLD) return;
      drag.dragged = true;
      setIsDragging(true);
    }

    const size = getRealSize();
    const bounds = measureCurrentBounds(size);
    const nextPos = clampLauncherPosition(
      {
        x: drag.initialX + dx,
        y: drag.initialY + dy,
      },
      bounds,
    );

    // Update currentPosRef immediately so endDrag has accurate final coordinates
    // regardless of React state batching
    currentPosRef.current = nextPos;
    setPos(nextPos);
  };

  const endDrag = (e: React.PointerEvent<HTMLDivElement>, cancelled = false) => {
    const drag = dragStateRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;

    // Clear drag state FIRST before releasing pointer capture
    // so that lostpointercapture / pointercancel cannot trigger duplicate processing
    const hadDragged = drag.dragged;
    dragStateRef.current = null;
    setIsDragging(false);

    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {}

    if (hadDragged) {
      // It was a drag: prevent opening chat, snap to nearest edge, persist position to account workspace
      justDraggedRef.current = true;
      setTimeout(() => {
        justDraggedRef.current = false;
      }, 300);

      const size = getRealSize();
      const bounds = measureCurrentBounds(size);
      const snappedPos = snapLauncherToEdge(currentPosRef.current, bounds);
      currentPosRef.current = snappedPos;
      setPos(snappedPos);

      updateWorkspace((prev) => ({
        ...prev,
        launcherPosition: snappedPos,
      }));
    } else if (!cancelled) {
      // It was a clean tap! Open chat
      triggerOpenChat();
    }
  };

  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    endDrag(e, false);
  };

  const onPointerCancel = (e: React.PointerEvent<HTMLDivElement>) => {
    endDrag(e, true);
  };

  const onClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (justDraggedRef.current) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    triggerOpenChat();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      triggerOpenChat();
    }
  };

  return (
    <div
      ref={launcherRef}
      className={`assistant-launcher ${isDragging ? "dragging" : ""}`}
      style={{
        left: `${pos.x}px`,
        top: `${pos.y}px`,
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
      onLostPointerCapture={onPointerCancel}
      onClick={onClick}
      onKeyDown={onKeyDown}
      role="region"
      aria-label="Bạn đồng hành AI"
    >
      <Mascot
        directions={`/mobile/mascot-${mascot}-directions.png`}
        reactions={`/mobile/mascot-${mascot}-reactions.png`}
        size={44}
        label="Gia sư AI"
      />
      <span className="assistant-badge" aria-hidden="true">
        AI
      </span>
    </div>
  );
}
