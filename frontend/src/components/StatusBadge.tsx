import type { FieldStatus } from "../api/types";
import { statusDisplay } from "../lib/status";

/**
 * A status pill showing icon + word + color together (never color alone), so it is
 * readable for colorblind users and screen readers alike.
 */
export function StatusBadge({ status }: { status: FieldStatus }) {
  const d = statusDisplay(status);
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border-2 px-3 py-1 text-base font-semibold ${d.badgeClass}`}
    >
      <span aria-hidden="true">{d.icon}</span>
      <span>{d.word}</span>
    </span>
  );
}
