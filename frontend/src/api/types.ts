// TypeScript shapes mirroring the backend Pydantic models in backend/app/models.py.
//
// In a full build these are generated from the backend's OpenAPI schema with
// `npm run gen:api` (openapi-typescript -> src/api/schema.d.ts). They are hand-written
// here so the app type-checks and runs without the backend running first; if a type ever
// disagrees with the server, fix the Pydantic model and regenerate rather than editing
// around it. Keep this file in sync with models.py.

export type FieldStatus =
  | "match"
  | "review"
  | "mismatch"
  | "not_found"
  | "not_required";

export type BeverageType = "beer" | "wine" | "spirits";

export interface FieldResult {
  field: string;
  label: string;
  expected: string | null;
  found: string | null;
  status: FieldStatus;
  reason: string;
  confidence: number;
}

export interface WarningSubCheck {
  status: FieldStatus;
  reason: string;
}

export interface WarningResult {
  found: boolean;
  overall: FieldStatus;
  wording: WarningSubCheck;
  capitals: WarningSubCheck;
  bold: WarningSubCheck;
  found_text: string | null;
  note: string | null;
}

export interface VerificationResult {
  overall: FieldStatus;
  fields: FieldResult[];
  warning: WarningResult;
  timings_ms: Record<string, number>;
  image_readable: boolean;
  message: string | null;
}

export interface ApplicationData {
  beverage_type: BeverageType;
  brand_name?: string;
  class_type?: string;
  alcohol_content?: string;
  net_contents?: string;
  bottler_name_address?: string;
  country_of_origin?: string;
}

export type BatchStatusValue = "queued" | "running" | "done" | "failed";

export interface BatchItemResult {
  image_filename: string;
  overall: FieldStatus;
  result: VerificationResult | null;
  error: string | null;
}

export interface BatchCreateResponse {
  batch_id: string;
  total: number;
  problems: string[];
}

export interface BatchStatusResponse {
  batch_id: string;
  status: BatchStatusValue;
  done: number;
  total: number;
  results: BatchItemResult[];
}
