import { useEffect, useMemo, useState } from "react";

import type { ApplicationData, BeverageType } from "../api/types";
import { ApiError } from "../api/client";
import { ErrorMessage } from "../components/ErrorMessage";
import { FileDrop } from "../components/FileDrop";
import { ResultsView } from "../components/ResultsView";
import { Spinner } from "../components/Spinner";
import { useVerify } from "../hooks/useVerify";

// The application form fields, in a sensible order. `requiredFor` says which beverage
// types require the field, so we can show a "Required" hint (country is import-only).
const FIELDS: {
  key: keyof Omit<ApplicationData, "beverage_type">;
  label: string;
  placeholder: string;
  requiredFor: BeverageType[];
}[] = [
  { key: "brand_name", label: "Brand name", placeholder: "Stone's Throw", requiredFor: ["beer", "wine", "spirits"] },
  { key: "class_type", label: "Class / type", placeholder: "Kentucky Straight Bourbon Whiskey", requiredFor: ["beer", "wine", "spirits"] },
  { key: "alcohol_content", label: "Alcohol content", placeholder: "45% Alc./Vol.", requiredFor: ["spirits"] },
  { key: "net_contents", label: "Net contents", placeholder: "750 mL", requiredFor: ["beer", "wine", "spirits"] },
  { key: "bottler_name_address", label: "Bottler / producer name & address", placeholder: "Old Tom Distillery, Louisville, KY", requiredFor: ["beer", "wine", "spirits"] },
  { key: "country_of_origin", label: "Country of origin (imports only)", placeholder: "Scotland", requiredFor: [] },
];

export function SingleCheck() {
  const [beverageType, setBeverageType] = useState<BeverageType>("spirits");
  const [values, setValues] = useState<Record<string, string>>({});
  const [image, setImage] = useState<File | null>(null);
  const verify = useVerify();

  // Build (and clean up) the preview URL for the chosen image.
  const imageUrl = useMemo(() => (image ? URL.createObjectURL(image) : undefined), [image]);
  useEffect(() => () => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
  }, [imageUrl]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!image) return;
    const application: ApplicationData = { beverage_type: beverageType, ...values };
    verify.mutate({ image, application });
  }

  const errorMessage =
    verify.error instanceof ApiError
      ? verify.error.message
      : verify.error
        ? "Something went wrong reading the label. Please try again."
        : null;

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="space-y-5">
        <FileDrop
          label="Label image"
          accept="image/*"
          hint="A clear, straight photo works best. JPG or PNG."
          file={image}
          onSelect={setImage}
        />

        {imageUrl && (
          <img
            src={imageUrl}
            alt="Preview of the label you chose"
            className="max-h-64 rounded-lg border border-gray-300"
          />
        )}

        {/* Beverage type first — it decides which fields are required. */}
        <div>
          <label htmlFor="beverage" className="mb-2 block text-lg font-semibold">
            Beverage type
          </label>
          <select
            id="beverage"
            value={beverageType}
            onChange={(e) => setBeverageType(e.target.value as BeverageType)}
            className="min-h-[44px] w-full rounded-md border-2 border-gray-400 bg-white px-3 text-lg"
          >
            <option value="spirits">Spirits</option>
            <option value="wine">Wine</option>
            <option value="beer">Beer</option>
          </select>
        </div>

        <fieldset className="space-y-4">
          <legend className="text-lg font-semibold">Application details</legend>
          {FIELDS.map((f) => {
            const required = f.requiredFor.includes(beverageType);
            return (
              <div key={f.key}>
                <label htmlFor={f.key} className="mb-1 block text-lg">
                  {f.label}
                  {required && <span className="ml-2 text-base text-gray-600">(required)</span>}
                </label>
                <input
                  id={f.key}
                  type="text"
                  placeholder={f.placeholder}
                  value={values[f.key] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                  className="min-h-[44px] w-full rounded-md border-2 border-gray-400 px-3 text-lg"
                />
              </div>
            );
          })}
        </fieldset>

        <button
          type="submit"
          disabled={!image || verify.isPending}
          className="min-h-[56px] w-full rounded-lg bg-blue-700 px-6 text-xl font-bold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-gray-400"
        >
          {verify.isPending ? "Reading label…" : "Check label"}
        </button>

        {verify.isPending && <Spinner label="Reading label…" />}
        {errorMessage && <ErrorMessage message={errorMessage} />}
      </form>

      {verify.data && (
        <section aria-label="Results">
          <h2 className="mb-3 text-2xl font-bold">Results</h2>
          <ResultsView result={verify.data} imageUrl={imageUrl} />
        </section>
      )}
    </div>
  );
}
