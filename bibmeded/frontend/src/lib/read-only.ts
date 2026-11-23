"use client";

import { useEffect, useState } from "react";
import api, { isPagesDemo } from "@/lib/api";

export const QUICK_START_URL = "https://ata381.github.io/BibMedEd/deploy/#quick-start";

let readOnlyRequest: Promise<boolean> | null = null;

// Fails closed: if the config can't be read, the UI assumes a read-only demo.
export function fetchReadOnly(): Promise<boolean> {
  if (isPagesDemo) return Promise.resolve(true);
  readOnlyRequest ??= api
    .get<{ read_only?: boolean }>("/api/config")
    .then((res) => res.data.read_only !== false)
    .catch(() => true);
  return readOnlyRequest;
}

/** `null` until `/api/config` resolves; callers should treat `null` as not writable. */
export function useReadOnly(): boolean | null {
  const [readOnly, setReadOnly] = useState<boolean | null>(isPagesDemo ? true : null);
  useEffect(() => {
    let active = true;
    fetchReadOnly().then((value) => {
      if (active) setReadOnly(value);
    });
    return () => {
      active = false;
    };
  }, []);
  return readOnly;
}
