import type { FieldResult } from "../api/types";
import { StatusBadge } from "./StatusBadge";

/**
 * One field's result: the field name, what the application says vs what the label says,
 * the status badge, and a one-line reason. Laid out as a card so each field is easy to
 * scan — no dense tables for the single-label view.
 */
export function FieldResultCard({ result }: { result: FieldResult }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xl font-bold">{result.label}</h3>
        <StatusBadge status={result.status} />
      </div>
      <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div>
          <dt className="text-base text-gray-600">Application says</dt>
          <dd className="text-lg font-medium">{result.expected ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-base text-gray-600">Label says</dt>
          <dd className="text-lg font-medium">{result.found ?? "—"}</dd>
        </div>
      </dl>
      <p className="mt-2 text-lg text-gray-700">{result.reason}</p>
    </div>
  );
}
