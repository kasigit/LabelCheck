import { useState } from "react";

import { BatchCheck } from "./pages/BatchCheck";
import { SingleCheck } from "./pages/SingleCheck";

type Tab = "single" | "batch";

/**
 * The whole app is two large, always-visible tabs — no hidden menus. The header states
 * plainly what the tool does and that the agent makes the final call.
 */
export function App() {
  const [tab, setTab] = useState<Tab>("single");

  const tabClass = (active: boolean) =>
    `flex-1 min-h-[56px] text-xl font-bold border-b-4 ${
      active
        ? "border-blue-700 text-blue-700"
        : "border-transparent text-gray-600 hover:text-gray-900"
    }`;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6">
        <h1 className="text-3xl font-bold">LabelCheck</h1>
        <p className="mt-1 text-lg text-gray-700">
          Check an alcohol label against its application. The tool flags differences; you
          make the final call.
        </p>
      </header>

      <nav className="mb-6 flex gap-2" role="tablist" aria-label="Choose what to check">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "single"}
          className={tabClass(tab === "single")}
          onClick={() => setTab("single")}
        >
          Check one label
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "batch"}
          className={tabClass(tab === "batch")}
          onClick={() => setTab("batch")}
        >
          Check a batch
        </button>
      </nav>

      <main>{tab === "single" ? <SingleCheck /> : <BatchCheck />}</main>
    </div>
  );
}
