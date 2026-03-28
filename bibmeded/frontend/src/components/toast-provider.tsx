"use client";

import { Toaster } from "react-hot-toast";

export function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 5000,
        style: {
          background: "#191c1e",
          color: "#f7f9fb",
          fontSize: "13px",
          fontFamily: "'Manrope', sans-serif",
          fontWeight: 600,
        },
        error: {
          iconTheme: { primary: "#ef4444", secondary: "#f7f9fb" },
        },
        success: {
          iconTheme: { primary: "#22c55e", secondary: "#f7f9fb" },
        },
      }}
    />
  );
}
