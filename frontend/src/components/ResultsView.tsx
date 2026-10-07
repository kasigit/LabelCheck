import type { VerificationResult } from "../api/types";
import { statusDisplay } from "../lib/status";
import { ErrorMessage } from "./ErrorMessage";
import { FieldResultCard } from "./FieldResultCard";
import { WarningSection } from "./WarningSection";

interface ResultsViewProps {
  result: VerificationResult;
  /** Preview of the label image, shown beside the results so the agent can eyeball it. */
  imageUrl?: string;
}

/**
 * The full single-label result: an overall banner, the label image beside the per-field
 * cards, and the Government Warning section. Used both after a single check and when
 * drilling into one row of a batch.
 */
export function ResultsView({ result, imageUrl }: ResultsViewProps) {
  if (!result.image_readable) {
    return <ErrorMessage message={result.message ?? "We couldn't read this image."} />;
  }

  const overall = statusDisplay(result.overall);

  return (
    <div className="space-y-5">
      <div
        className={`rounded-lg border-2 p-4 text-xl font-bold ${overall.badgeClass}`}
        aria-live="polite"
      >
        <span aria-hidden="true" className="mr-2">
          {overall.icon}
        </span>
        Overall: {overall.word}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[320px_1fr]">
        {imageUrl && (
          <div className="lg:sticky lg:top-4 lg:self-start">
            <img
              src={imageUrl}
              alt="The label you uploaded"
              className="w-full rounded-lg border border-gray-300"
            />
          </div>
        )}

        <div className="space-y-4">
          {result.fields.map((f) => (
            <FieldResultCard key={f.field} result={f} />
          ))}
          <WarningSection warning={result.warning} />
        </div>
      </div>
    </div>
  );
}
