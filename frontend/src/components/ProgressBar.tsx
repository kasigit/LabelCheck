/**
 * A labelled progress bar. The text ("143 of 212 checked") is shown alongside the bar so
 * progress is clear without relying on the visual width alone.
 */
export function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div>
      <div className="mb-1 text-lg font-semibold" aria-live="polite">
        {done} of {total} checked
      </div>
      <div
        className="h-5 w-full overflow-hidden rounded-full bg-gray-200"
        role="progressbar"
        aria-valuenow={done}
        aria-valuemin={0}
        aria-valuemax={total}
      >
        <div
          className="h-full rounded-full bg-blue-600 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
