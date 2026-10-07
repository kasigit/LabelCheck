/**
 * A spinner with a visible text label (e.g. "Reading label…"). The text matters: it tells
 * non-technical users the app is working, not frozen.
 */
export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 text-lg text-gray-700" role="status">
      <span
        aria-hidden="true"
        className="h-6 w-6 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600"
      />
      <span>{label}</span>
    </div>
  );
}
