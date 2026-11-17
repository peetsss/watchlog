import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./api";
import type { components } from "./api-types";

export const ACCOUNT_QUERY_KEY = ["account"] as const;

type AccountEnvelope = components["schemas"]["AccountEnvelope"];

async function fetchAccount(): Promise<AccountEnvelope> {
  return unwrap<AccountEnvelope>(api.GET("/api/account"));
}

export function useAccount() {
  return useQuery({
    queryKey: ACCOUNT_QUERY_KEY,
    queryFn: fetchAccount,
    staleTime: 30_000,
  });
}

export async function resendVerification(email: string): Promise<void> {
  await unwrap(
    api.POST("/api/auth/resend-verification", {
      body: { email },
    }),
  );
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await unwrap(
    api.POST("/api/auth/change-password", {
      body: { current_password: currentPassword, new_password: newPassword },
    }),
  );
}

export async function changeEmail(newEmail: string, password: string): Promise<void> {
  await unwrap(
    api.POST("/api/auth/change-email", {
      body: { new_email: newEmail, password },
    }),
  );
}
