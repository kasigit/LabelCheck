import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ErrorMessage } from "./ErrorMessage";

describe("ErrorMessage", () => {
  it("renders the server message in an alert region", () => {
    render(<ErrorMessage message="This file isn't an image. Upload a JPG or PNG." />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("This file isn't an image. Upload a JPG or PNG.");
  });
});
