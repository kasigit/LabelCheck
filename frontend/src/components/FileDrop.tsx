import { useId, useRef, useState } from "react";

interface FileDropProps {
  label: string;
  accept: string;
  /** Human hint under the label, e.g. "JPG or PNG". */
  hint?: string;
  file: File | null;
  onSelect: (file: File | null) => void;
}

/**
 * File picker with optional drag-and-drop. Per the accessibility rules a visible
 * "Choose file" button is always present (drag-and-drop is only a bonus), the control is
 * large, and the chosen filename is shown back in plain text.
 */
export function FileDrop({ label, accept, hint, file, onSelect }: FileDropProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0] ?? null;
    if (dropped) onSelect(dropped);
  }

  return (
    <div>
      <label htmlFor={inputId} className="mb-2 block text-lg font-semibold">
        {label}
      </label>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`rounded-lg border-2 border-dashed p-5 text-center ${
          dragOver ? "border-blue-600 bg-blue-50" : "border-gray-400 bg-white"
        }`}
      >
        <input
          id={inputId}
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(e) => onSelect(e.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="min-h-[44px] rounded-md bg-gray-800 px-5 py-2 text-lg font-semibold text-white hover:bg-gray-700"
        >
          Choose file
        </button>
        {hint && <p className="mt-2 text-base text-gray-600">{hint}</p>}
        <p className="mt-2 text-base text-gray-800">
          {file ? (
            <>
              Selected: <span className="font-semibold">{file.name}</span>
            </>
          ) : (
            "No file chosen yet. You can also drag a file here."
          )}
        </p>
      </div>
    </div>
  );
}
