import { api, unwrap } from "./api";
import type { components } from "./api-types";

type SessionEnvelope = components["schemas"]["SessionEnvelope"];

export async function createGuest(displayName: string): Promise<SessionEnvelope> {
  return unwrap<SessionEnvelope>(
    api.POST("/api/auth/guest", {
      body: { display_name: displayName },
    }),
  );
}
