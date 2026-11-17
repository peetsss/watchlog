import { api, unwrap } from "./api";

export async function verifyEmail(token: string): Promise<void> {
  await unwrap(
    api.POST("/api/auth/verify-email", {
      body: { token },
    }),
  );
}

export async function forgotPassword(email: string): Promise<void> {
  await unwrap(
    api.POST("/api/auth/forgot-password", {
      body: { email },
    }),
  );
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await unwrap(
    api.POST("/api/auth/reset-password", {
      body: { token, new_password: newPassword },
    }),
  );
}
