/**
 * A plain-English error banner. It shows what happened and what to do, never a stack
 * trace or an HTTP status code (the backend already phrases `detail` for humans).
 */
export function ErrorMessage({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border-2 border-status-mismatch bg-red-50 p-4 text-lg text-status-mismatch"
    >
      <span aria-hidden="true" className="mr-2 font-bold">
        ✗
      </span>
      {message}
    </div>
  );
}
