import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { VerificationResult } from "../api/types";
import { SingleCheck } from "./SingleCheck";

// Mock at the api/client boundary (not fetch), per the testing conventions.
vi.mock("../api/client", () => ({
  ApiError: class ApiError extends Error {},
  verifyLabel: vi.fn(),
}));
import { verifyLabel } from "../api/client";

const ALL_MATCH: VerificationResult = {
  overall: "match",
  fields: [
    {
      field: "brand_name",
      label: "Brand name",
      expected: "Stone's Throw",
      found: "STONE'S THROW",
      status: "match",
      reason: "Matches (capitalization differs only).",
      confidence: 0.95,
    },
  ],
  warning: {
    found: true,
    overall: "match",
    wording: { status: "match", reason: "Wording matches." },
    capitals: { status: "match", reason: "All caps." },
    bold: { status: "match", reason: "Bold." },
    found_text: "GOVERNMENT WARNING: ...",
    note: null,
  },
  timings_ms: { total: 300 },
  image_readable: true,
  message: null,
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SingleCheck />
    </QueryClientProvider>,
  );
}

describe("SingleCheck", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps the Check label button disabled until an image is chosen", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /check label/i })).toBeDisabled();
  });

  it("shows per-field results after a successful check", async () => {
    vi.mocked(verifyLabel).mockResolvedValue(ALL_MATCH);
    renderPage();

    const file = new File(["x"], "label.png", { type: "image/png" });
    await userEvent.upload(screen.getByLabelText(/label image/i), file);

    await userEvent.click(screen.getByRole("button", { name: /check label/i }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /results/i })).toBeInTheDocument(),
    );
    // The field result card renders the field name as a heading (distinct from the form label).
    expect(screen.getByRole("heading", { name: "Brand name" })).toBeInTheDocument();
    expect(screen.getByText(/overall: match/i)).toBeInTheDocument();
  });
});
