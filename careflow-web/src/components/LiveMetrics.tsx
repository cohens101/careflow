"use client";

import { useEffect, useState } from "react";

type Overview = {
  patients: number;
  encounters: number;
  conditions: number;
};

export default function LiveMetrics() {
  const [data, setData] = useState<Overview | null>(null);
  const [status, setStatus] = useState<
    "loading" | "ready" | "error"
  >("loading");

  useEffect(() => {
    const controller = new AbortController();

    async function loadMetrics() {
      try {
        const response = await fetch("/api/snowflake", {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Snowflake request failed");
        }

        const result: Overview = await response.json();

        if (
          ![
            result.patients,
            result.encounters,
            result.conditions,
          ].every(Number.isFinite)
        ) {
          throw new Error("Invalid analytics response");
        }

        if (!controller.signal.aborted) {
          setData(result);
          setStatus("ready");
        }
      } catch {
        if (!controller.signal.aborted) {
          setStatus("error");
        }
      }
    }

    void loadMetrics();
    return () => controller.abort();
  }, []);

  const format = (value: number) =>
    value.toLocaleString("en-US");

  const display = (value: number | undefined) =>
    value !== undefined
      ? format(value)
      : status === "loading"
        ? "Loading..."
        : "Unavailable";

  const metrics = [
    {
      label: "Synthetic Patients",
      value: display(data?.patients),
    },
    {
      label: "Total Encounters",
      value: display(data?.encounters),
    },
    {
      label: "Condition Records",
      value: display(data?.conditions),
    },
    {
      label: "Silver Quality Tests (snapshot)",
      value: "11 Passed",
    },
  ];

  return (
    <section aria-label="Healthcare metrics">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="rounded-2xl border border-slate-800 bg-slate-900 p-6"
          >
            <p className="text-sm text-slate-400">
              {metric.label}
            </p>
            <p className="mt-3 text-3xl font-semibold tracking-tight">
              {metric.value}
            </p>
          </div>
        ))}
      </div>

      <p
        className="mt-3 text-xs text-slate-400"
        aria-live="polite"
      >
        {status === "ready"
          ? "Live aggregate metrics retrieved from Snowflake."
          : status === "loading"
            ? "Connecting to Snowflake..."
            : "Snowflake metrics unavailable. Check server logs."}
      </p>
    </section>
  );
}
