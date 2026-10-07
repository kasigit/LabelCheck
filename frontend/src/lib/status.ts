// How each status is shown. Per the accessibility rules, status is always conveyed with
// an icon AND a word AND a color — never color alone.

import type { FieldStatus } from "../api/types";

export interface StatusDisplay {
  icon: string;
  word: string;
  /** Tailwind text-color class using the tokens from tailwind.config.js. */
  textClass: string;
  /** Tailwind background/border classes for badges and cards. */
  badgeClass: string;
}

export const STATUS_DISPLAY: Record<FieldStatus, StatusDisplay> = {
  match: {
    icon: "✓",
    word: "Match",
    textClass: "text-status-match",
    badgeClass: "bg-green-50 border-status-match text-status-match",
  },
  review: {
    icon: "⚠",
    word: "Needs review",
    textClass: "text-status-review",
    badgeClass: "bg-amber-50 border-status-review text-status-review",
  },
  mismatch: {
    icon: "✗",
    word: "Mismatch",
    textClass: "text-status-mismatch",
    badgeClass: "bg-red-50 border-status-mismatch text-status-mismatch",
  },
  not_found: {
    icon: "?",
    word: "Not found on label",
    textClass: "text-status-missing",
    badgeClass: "bg-gray-100 border-status-missing text-status-missing",
  },
  not_required: {
    icon: "–",
    word: "Not required",
    textClass: "text-status-missing",
    badgeClass: "bg-gray-100 border-status-missing text-status-missing",
  },
};

export function statusDisplay(status: FieldStatus): StatusDisplay {
  return STATUS_DISPLAY[status];
}
