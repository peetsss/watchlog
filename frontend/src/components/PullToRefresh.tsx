import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useToast } from "../state/Toast";

const THRESHOLD = 64;

export function PullToRefresh() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [distance, setDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const pullRef = useRef(0);
  const startY = useRef<number | null>(null);
  const active = useRef(false);

  useEffect(() => {
    const setPull = (value: number) => {
      pullRef.current = value;
      setDistance(value);
    };

    const onTouchStart = (event: TouchEvent) => {
      if (event.touches.length !== 1 || refreshing) return;
      if (window.scrollY > 0) return;
      if (document.querySelector('[role="dialog"]')) return;
      const target = event.target;
      if (target instanceof Element && target.closest("[data-no-pull]")) return;
      startY.current = event.touches[0].clientY;
      active.current = true;
    };

    const onTouchMove = (event: TouchEvent) => {
      if (!active.current || startY.current === null) return;
      if (event.touches.length !== 1) {
        active.current = false;
        setPull(0);
        return;
      }
      const delta = event.touches[0].clientY - startY.current;
      if (delta <= 0) {
        setPull(0);
        return;
      }
      if (window.scrollY > 0) {
        active.current = false;
        setPull(0);
        return;
      }
      event.preventDefault();
      setPull(Math.min(108, delta * 0.55));
    };

    const finish = () => {
      if (!active.current) return;
      active.current = false;
      startY.current = null;
      if (pullRef.current < THRESHOLD) {
        setPull(0);
        return;
      }
      setRefreshing(true);
      setPull(42);
      void queryClient
        .invalidateQueries()
        .then(() => queryClient.refetchQueries({ type: "active" }))
        .then(() => showToast("Refreshed."))
        .finally(() => {
          setRefreshing(false);
          setPull(0);
        });
    };

    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("touchend", finish);
    window.addEventListener("touchcancel", finish);

    return () => {
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", finish);
      window.removeEventListener("touchcancel", finish);
    };
  }, [queryClient, refreshing, showToast]);

  const visible = distance > 0 || refreshing;

  return (
    <div
      className="pull-refresh"
      style={{
        transform: `translate(-50%, ${Math.max(0, distance - 42)}px)`,
        opacity: visible ? Math.min(1, distance / 52) : 0,
      }}
      aria-hidden={!visible}
    >
      <span className="pull-refresh-pill">
        <Loader2 className={refreshing ? "spin" : undefined} size={14} />
        <span>{refreshing ? "Refreshing…" : distance >= THRESHOLD ? "Release to refresh" : "Pull to refresh"}</span>
      </span>
    </div>
  );
}
