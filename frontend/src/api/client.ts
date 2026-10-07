// The single place every network call goes through. Components and hooks never call
// `fetch` directly — this keeps error handling uniform and makes the API easy to mock in
// tests (we mock this module, not global fetch).

import type {
  ApplicationData,
  BatchCreateResponse,
  BatchStatusResponse,
  VerificationResult,
} from "./types";

const API_BASE = "/api";

/** Error carrying the server's plain-English `detail`, which the UI shows directly. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Turn a failed response into an ApiError with a human-readable message. */
async function toApiError(res: Response): Promise<ApiError> {
  let detail = "Something went wrong. Please try again.";
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    // Non-JSON error body; keep the friendly default.
  }
  return new ApiError(detail, res.status);
}

/** Verify a single label image against application data. */
export async function verifyLabel(
  image: File,
  application: ApplicationData,
): Promise<VerificationResult> {
  const form = new FormData();
  form.append("image", image);
  form.append("application", JSON.stringify(application));

  const res = await fetch(`${API_BASE}/verify`, { method: "POST", body: form });
  if (!res.ok) throw await toApiError(res);
  return res.json();
}

/** Start a batch run from a CSV file and a ZIP of images. */
export async function createBatch(
  csv: File,
  images: File,
): Promise<BatchCreateResponse> {
  const form = new FormData();
  form.append("csv", csv);
  form.append("images", images);

  const res = await fetch(`${API_BASE}/batch`, { method: "POST", body: form });
  if (!res.ok) throw await toApiError(res);
  return res.json();
}

/** Poll a batch's status and partial results. */
export async function getBatch(batchId: string): Promise<BatchStatusResponse> {
  const res = await fetch(`${API_BASE}/batch/${batchId}`);
  if (!res.ok) throw await toApiError(res);
  return res.json();
}

/** URL for downloading a batch's results as CSV (used as a plain link). */
export function batchExportUrl(batchId: string): string {
  return `${API_BASE}/batch/${batchId}/export.csv`;
}
