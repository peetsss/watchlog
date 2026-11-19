import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useActiveLobby } from "../lib/api-lobby";
import { useToast } from "../state/Toast";

export function ActiveLobbyNotifications() {
  const activeLobby = useActiveLobby().data ?? null;
  const location = useLocation();
  const { showToast } = useToast();
  const lastSeen = useRef<string | null>(null);

  useEffect(() => {
    if (!activeLobby) {
      lastSeen.current = null;
      return;
    }
    if (location.pathname === `/lobby/${activeLobby.uuid}`) return;
    if (lastSeen.current === activeLobby.uuid) return;

    lastSeen.current = activeLobby.uuid;
    const storageKey = `watchlog:lobby-toast:${activeLobby.uuid}`;
    try {
      if (sessionStorage.getItem(storageKey)) return;
      sessionStorage.setItem(storageKey, "1");
    } catch {
      // Session storage can be unavailable in privacy modes.
    }

    showToast(`${activeLobby.groupName ?? "A movie night"} is live.`, {
      label: "Join the room",
      href: `/lobby/${activeLobby.uuid}`,
    });
  }, [activeLobby, location.pathname, showToast]);

  return null;
}
