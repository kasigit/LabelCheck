import type { WarningResult } from "../api/types";
import { StatusBadge } from "./StatusBadge";

/**
 * The Government Warning gets its own prominent section with the three sub-checks
 * (wording / capitals / bold) shown separately, since each is a distinct legal rule.
 */
export function WarningSection({ warning }: { warning: WarningResult }) {
  const subChecks = [
    { name: "Exact wording", check: warning.wording },
    { name: "ALL CAPITALS prefix", check: warning.capitals },
    { name: "Bold prefix", check: warning.bold },
  ];

  return (
    <section className="rounded-lg border-2 border-gray-300 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xl font-bold">Government Health Warning</h3>
        <StatusBadge status={warning.overall} />
      </div>

      {!warning.found && (
        <p className="mt-2 text-lg text-status-mismatch">
          No Government Warning was found on this label. One is required on every alcohol
          label.
        </p>
      )}

      {warning.found && (
        <ul className="mt-3 space-y-2">
          {subChecks.map((s) => (
            <li
              key={s.name}
              className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-2"
            >
              <span className="text-lg font-medium">{s.name}</span>
              <StatusBadge status={s.check.status} />
              <span className="w-full text-base text-gray-700">{s.check.reason}</span>
            </li>
          ))}
        </ul>
      )}

      {warning.note && (
        <p className="mt-3 rounded bg-amber-50 p-2 text-base text-status-review">
          ⚠ {warning.note}
        </p>
      )}

      {warning.found_text && (
        <details className="mt-3 text-base text-gray-600">
          <summary className="cursor-pointer">Show the warning text we read</summary>
          <p className="mt-1 whitespace-pre-wrap">{warning.found_text}</p>
        </details>
      )}
    </section>
  );
}
