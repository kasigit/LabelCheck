import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProgressBar } from "./ProgressBar";

describe("ProgressBar", () => {
  it("shows '<done> of <total> checked'", () => {
    render(<ProgressBar done={143} total={212} />);
    expect(screen.getByText("143 of 212 checked")).toBeInTheDocument();
  });

  it("exposes progress to assistive tech", () => {
    render(<ProgressBar done={5} total={10} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "5");
    expect(bar).toHaveAttribute("aria-valuemax", "10");
  });
});
