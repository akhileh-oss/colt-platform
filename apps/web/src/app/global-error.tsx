"use client";

/**
 * Catches an error thrown by the root layout itself, where `error.tsx` cannot help (Next.js
 * requires this to render its own <html>/<body> since the layout that would have is what
 * failed). Kept deliberately minimal — no design-system imports, since those are exactly what
 * might have caused the failure.
 */
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "3rem", textAlign: "center" }}>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 600 }}>Something went wrong</h1>
        <p style={{ color: "#666", marginTop: "0.5rem" }}>
          The application failed to load. Try again, or contact support if this persists.
        </p>
        <button
          onClick={reset}
          style={{
            marginTop: "1.5rem",
            padding: "0.5rem 1rem",
            borderRadius: "0.375rem",
            border: "1px solid #ccc",
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
