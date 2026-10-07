import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { FieldStatus } from "../api/types";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  // Every status must render its word (icon + word + color, never color alone).
  const cases: [FieldStatus, string][] = [
    ["match", "Match"],
    ["review", "Needs review"],
    ["mismatch", "Mismatch"],
    ["not_found", "Not found on label"],
    ["not_required", "Not required"],
  ];

  it.each(cases)("renders the word for %s", (status, word) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(word)).toBeInTheDocument();
  });
});
