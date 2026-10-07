import { useMemo, useState } from "react";

import { ApiError, batchExportUrl } from "../api/client";
import type { BatchItemResult, FieldStatus } from "../api/types";
import { ErrorMessage } from "../components/ErrorMessage";
import { FileDrop } from "../components/FileDrop";
import { ProgressBar } from "../components/ProgressBar";
import { ResultsView } from "../components/ResultsView";
import { StatusBadge } from "../components/StatusBadge";
import { useBatchStatus, useCreateBatch } from "../hooks/useBatch";

const FILTERS: { label: string; value: FieldStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Mismatch", value: "mismatch" },
  { label: "Needs review", value: "review" },
  { label: "Not found", value: "not_found" },
  { label: "Match", value: "match" },
];

export function BatchCheck() {
  const [csv, setCsv] = useState<File | null>(null);
  const [zip, setZip] = useState<File | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [filter, setFilter] = useState<FieldStatus | "all">("all");
  const [openRow, setOpenRow] = useState<BatchItemResult | null>(null);

  const create = useCreateBatch();
  const status = useBatchStatus(batchId);

  function start(e: React.FormEvent) {
    e.preventDefault();
    if (!csv || !zip) return;
    create.mutate(
      { csv, images: zip },
      { onSuccess: (res) => setBatchId(res.batch_id) },
    );
  }

  const filtered = useMemo(() => {
    const rows = status.data?.results ?? [];
    return filter === "all" ? rows : rows.filter((r) => r.overall === filter);
  }, [status.data?.results, filter]);

  const createError =
    create.error instanceof ApiError
      ? create.error.message
      : create.error
        ? "Something went wrong starting the batch. Please try again."
        : null;

  // A single row's detail view.
  if (openRow) {
    return (
      <div className="space-y-4">
        <button
          type="button"
          onClick={() => setOpenRow(null)}
          className="min-h-[44px] rounded-md bg-gray-200 px-4 text-lg font-semibold hover:bg-gray-300"
        >
          ← Back to all results
        </button>
        <h2 className="text-2xl font-bold">{openRow.image_filename}</h2>
        {openRow.result ? (
          <ResultsView result={openRow.result} />
        ) : (
          <ErrorMessage message={openRow.error ?? "This label could not be processed."} />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <form onSubmit={start} className="space-y-5">
        <FileDrop
          label="Applications file (CSV)"
          accept=".csv,text/csv"
          hint="One row per label, matching the batch template."
          file={csv}
          onSelect={setCsv}
        />
        <FileDrop
          label="Label images (ZIP)"
          accept=".zip,application/zip"
          hint="A ZIP containing every label image named in the CSV."
          file={zip}
          onSelect={setZip}
        />
        <button
          type="submit"
          disabled={!csv || !zip || create.isPending}
          className="min-h-[56px] w-full rounded-lg bg-blue-700 px-6 text-xl font-bold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-gray-400"
        >
          {create.isPending ? "Checking…" : "Check all labels"}
        </button>
        {createError && <ErrorMessage message={createError} />}
      </form>

      {/* Validation problems found up front. */}
      {create.data && create.data.problems.length > 0 && (
        <div className="rounded-lg border-2 border-status-review bg-amber-50 p-4">
          <p className="text-lg font-semibold text-status-review">
            {create.data.total} labels ready. {create.data.problems.length} problem
            {create.data.problems.length === 1 ? "" : "s"} found:
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-6 text-base">
            {create.data.problems.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      {batchId && status.data && (
        <section className="space-y-4" aria-label="Batch results">
          <ProgressBar done={status.data.done} total={status.data.total} />

          <div className="flex flex-wrap items-center gap-3">
            <span className="text-lg font-semibold">Show:</span>
            {FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                onClick={() => setFilter(f.value)}
                className={`min-h-[44px] rounded-md border-2 px-4 text-lg ${
                  filter === f.value
                    ? "border-blue-700 bg-blue-700 text-white"
                    : "border-gray-400 bg-white"
                }`}
              >
                {f.label}
              </button>
            ))}
            <a
              href={batchExportUrl(batchId)}
              className="ml-auto min-h-[44px] rounded-md bg-gray-800 px-4 py-2 text-lg font-semibold text-white hover:bg-gray-700"
            >
              Download results (CSV)
            </a>
          </div>

          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b-2 border-gray-300 text-lg">
                <th className="py-2">Label file</th>
                <th className="py-2">Overall</th>
                <th className="py-2">Details</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.image_filename} className="border-b border-gray-200">
                  <td className="py-2 text-lg">{row.image_filename}</td>
                  <td className="py-2">
                    <StatusBadge status={row.overall} />
                  </td>
                  <td className="py-2">
                    <button
                      type="button"
                      onClick={() => setOpenRow(row)}
                      className="min-h-[44px] rounded-md border-2 border-gray-400 px-4 text-lg hover:bg-gray-100"
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-4 text-lg text-gray-600">
                    No labels with this status.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
