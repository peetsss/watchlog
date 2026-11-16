import { useQuery } from "@tanstack/react-query";
import { type HomeView, homeToView } from "./adapters";
import { api, ApiError, unwrap } from "./api";
import type { components } from "./api-types";
import { homeKeys } from "./query-keys";

function retryUnlessDenied(failureCount: number, error: Error): boolean {
  if (error instanceof ApiError && [401, 403, 404].includes(error.status)) return false;
  return failureCount < 1;
}

async function fetchHome(): Promise<HomeView> {
  const payload = await unwrap<components["schemas"]["HomeResponse"]>(api.GET("/api/home"));
  return homeToView(payload);
}

export function useHome() {
  return useQuery({
    queryKey: homeKeys.all,
    queryFn: fetchHome,
    staleTime: 15_000,
    retry: retryUnlessDenied,
  });
}
