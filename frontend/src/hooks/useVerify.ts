import { useMutation } from "@tanstack/react-query";

import { verifyLabel } from "../api/client";
import type { ApplicationData } from "../api/types";
import { downscaleImage } from "../lib/image";

/**
 * Mutation for a single-label check. Downscales the image client-side first (faster
 * uploads) and then calls the API. Server state lives in TanStack Query, not in component
 * state, per the frontend conventions.
 */
export function useVerify() {
  return useMutation({
    mutationFn: async (vars: { image: File; application: ApplicationData }) => {
      const smaller = await downscaleImage(vars.image);
      return verifyLabel(smaller, vars.application);
    },
  });
}
