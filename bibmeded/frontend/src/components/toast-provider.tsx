"use client";

import { Toaster } from "react-hot-toast";

export function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      // react-hot-toast defaults to aria-live="off" — make success/info toasts
      // polite (announce when the screen reader is idle) and errors assertive
      // (announce immediately).
      toastOptions={{
        duration: 5000,
        ariaProps: {
          role: "status",
          "aria-live": "polite",
        },
        error: {
          iconTheme: { primary: "var(--color-danger)", secondary: "var(--color-on-danger)" },
          ariaProps: {
            role: "alert",
            "aria-live": "assertive",
          },
        },
        success: {
          iconTheme: { primary: "var(--color-accent)", secondary: "var(--color-on-accent)" },
        },
        style: {
          background: "var(--color-ink)",
          color: "var(--color-on-ink)",
          border: "1px solid var(--color-outline-strong)",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-lg)",
          fontSize: "14px",
          fontFamily: "var(--font-sans)",
          fontWeight: 500,
          maxWidth: "26rem",
        },
      }}
    />
  );
}
