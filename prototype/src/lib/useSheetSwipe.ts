import { useCallback, useEffect, useRef } from "react";

type DragState = {
  pointerId: number | null;
  startX: number;
  startY: number;
  lastY: number;
  lastT: number;
  vy: number;
  active: boolean;
  started: boolean;
};

export function useSheetSwipe(open: boolean, onClose: () => void) {
  const state = useRef<DragState>({
    pointerId: null,
    startX: 0,
    startY: 0,
    lastY: 0,
    lastT: 0,
    vy: 0,
    active: false,
    started: false,
  });
  const sheetRef = useRef<HTMLElement | null>(null);
  const closeTimer = useRef<number | null>(null);

  const resetSheet = useCallback(() => {
    const sheet = sheetRef.current;
    if (sheet) {
      sheet.style.transition = "";
      sheet.style.transform = "";
      sheet.style.opacity = "";
    }
    state.current.active = false;
    state.current.started = false;
    state.current.pointerId = null;
    state.current.vy = 0;
  }, []);

  useEffect(() => {
    if (open) {
      if (closeTimer.current) {
        window.clearTimeout(closeTimer.current);
        closeTimer.current = null;
      }
      return;
    }
    resetSheet();
  }, [open, resetSheet]);

  useEffect(
    () => () => {
      if (closeTimer.current) window.clearTimeout(closeTimer.current);
    },
    [],
  );

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!window.matchMedia("(max-width: 760px)").matches) return;
    if (event.pointerType === "mouse" && event.button !== 0) return;
    if ((event.target as HTMLElement).closest("button, a, input, select, textarea")) return;
    if (state.current.active) return;

    const sheet = (event.currentTarget as HTMLElement).closest(".detail-sheet") as HTMLElement | null;
    if (!sheet) return;

    sheetRef.current = sheet;
    state.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      lastY: event.clientY,
      lastT: performance.now(),
      vy: 0,
      active: true,
      started: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = state.current;
    const sheet = sheetRef.current;
    if (!drag.active || !sheet || drag.pointerId !== event.pointerId) return;

    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;

    if (!drag.started) {
      if (Math.abs(dy) < 8 || Math.abs(dy) < Math.abs(dx)) return;
      if (dy < 0) {
        drag.active = false;
        return;
      }
      drag.started = true;
      sheet.style.transition = "none";
    }

    const now = performance.now();
    const dt = now - drag.lastT;
    if (dt > 0) drag.vy = ((event.clientY - drag.lastY) / dt) * 1000;
    drag.lastY = event.clientY;
    drag.lastT = now;

    const offset = Math.max(0, dy);
    sheet.style.transform = `translateY(${offset}px)`;
    sheet.style.opacity = `${1 - Math.min(offset / 500, 0.3)}`;
    event.preventDefault();
  };

  const onPointerEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = state.current;
    const sheet = sheetRef.current;
    if (!drag.active || drag.pointerId !== event.pointerId) return;

    const dy = drag.lastY - drag.startY;
    const vy = drag.vy;
    const shouldClose = drag.started && (dy > 90 || (vy > 450 && dy > 24));

    if (shouldClose && sheet) {
      sheet.style.transition =
        "transform 170ms cubic-bezier(0.2, 0.8, 0.2, 1), opacity 170ms ease";
      sheet.style.transform = "translateY(100%)";
      sheet.style.opacity = "0";
      drag.active = false;
      drag.started = false;
      drag.pointerId = null;
      closeTimer.current = window.setTimeout(() => {
        closeTimer.current = null;
        onClose();
      }, 165);
      return;
    }

    resetSheet();
  };

  const onPointerCancel = (event: React.PointerEvent<HTMLDivElement>) => {
    if (state.current.pointerId !== event.pointerId) return;
    resetSheet();
  };

  return { onPointerDown, onPointerMove, onPointerUp: onPointerEnd, onPointerCancel };
}
