import { useMutation, useQuery } from "@tanstack/react-query";

import { createBatch, getBatch } from "../api/client";

/** Mutation to start a batch from a CSV file + a ZIP of images. */
export function useCreateBatch() {
  return useMutation({
    mutationFn: (vars: { csv: File; images: File }) =>
      createBatch(vars.csv, vars.images),
  });
}

/**
 * Poll a batch's status once a second, showing partial results as they arrive, and stop
 * polling when the run is done or failed (so we don't hammer the server forever).
 */
export function useBatchStatus(batchId: string | null) {
  return useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => getBatch(batchId as string),
    enabled: batchId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 1000;
    },
  });
}
