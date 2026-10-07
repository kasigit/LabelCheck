// Vitest setup: adds jest-dom matchers (toBeInTheDocument, etc.) to expect().
import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom doesn't implement object URLs; stub them so components that preview a chosen
// image file can render in tests.
if (typeof URL.createObjectURL !== "function") {
  URL.createObjectURL = vi.fn(() => "blob:mock-url");
  URL.revokeObjectURL = vi.fn();
}
