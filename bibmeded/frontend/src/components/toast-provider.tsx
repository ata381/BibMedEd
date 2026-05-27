"use client";

import { Toaster } from "react-hot-toast";

export function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      // react-hot-toast defaults to aria-live="off" — make success/info toasts
      // polite (announce when the screen reader is idle) and errors assertive
      // (announce immediately). Without this, "Publication excluded" and
      // "Bulk exclude failed" silently never reach screen-reader users.
      toastOptions={{
        duration: 5000,
        ariaProps: {
          role: "status",
          "aria-live": "polite",
        },
        error: {
          iconTheme: { primary: "#ef4444", secondary: "#f7f9fb" },
          ariaProps: {
            role: "alert",
            "aria-live": "assertive",
          },
        },
        success: {
          iconTheme: { primary: "#22c55e", secondary: "#f7f9fb" },
        },
        style: {
          background: "#191c1e",
          color: "#f7f9fb",
          fontSize: "13px",
          fontFamily: "'Manrope', sans-serif",
          fontWeight: 600,
        },
      }}
    />
  );
}
