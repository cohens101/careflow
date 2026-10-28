"use client";

import { useEffect, useState } from "react";

type Encounter = {
  category: string;
  count: number;
};

type Diagnosis = {
  name: string;
  records: number;
};

type ChartData = {
  encounters: Encounter[];
  diagnoses: Diagnosis[];
};

const encounterLabels: Record<string, string> = {
  AMB: "Ambulatory",
  EMER: "Emergency",
  IMP: "Inpatient",
  HH: "Home Health",
  VR: "Virtual",
};

export default function LiveCharts() {
  const [data, setData] = useState<ChartData | null>(null);
  const [status, setStatus] = useState<
    "loading" | "ready" | "error"
  >("loading");

  useEffect(() => {
    const controller = new AbortController();

    async function loadCharts() {
      try {
        const response = await fetch("/api/snowflake/charts", {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Chart request failed");
        }

        const result: ChartData = await response.json();

        if (
          !Array.isArray(result.encounters) ||
          !Array.isArray(result.diagnoses) ||
          !result.encounters.every(
            (x) =>
              typeof x.category === "string" &&
              Number.isFinite(x.count) &&
              x.count >= 0
          ) ||
          !result.diagnoses.every(
            (x) =>
              typeof x.name === "string" &&
              Number.isFinite(x.records) &&
              x.records >= 0
          )
        ) {
          throw new Error("Invalid chart data");
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

    void loadCharts();
    return () => controller.abort();
  }, []);

  if (status !== "ready" || !data) {
    return (
      <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-8">
        <p className="text-sm text-slate-400" role="status">
          {status === "loading"
            ? "Loading clinical analytics from Snowflake..."
            : "Clinical analytics unavailable. Check server logs."}
        </p>
      </section>
    );
  }

  const totalEncounters = data.encounters.reduce(
    (sum, item) => sum + item.count,
    0
  );

  const format = (value: number) =>
    value.toLocaleString("en-US");

  return (
    <section
      className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2"
      aria-label="Live clinical analytics"
    >
      <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="text-lg font-semibold">
          Encounter Distribution
        </h2>

        <p className="mt-1 text-sm text-slate-400">
          Historical encounters · Snowflake Gold
        </p>

        <div className="mt-8 space-y-6">
          {data.encounters.map((item) => {
            const percentage =
              totalEncounters > 0
                ? (item.count / totalEncounters) * 100
                : 0;

            return (
              <div key={item.category}>
                <div className="mb-2 flex justify-between gap-3 text-sm">
                  <span>
                    {encounterLabels[item.category] ??
                      item.category}
                  </span>

                  <span className="text-slate-400">
                    {format(item.count)} (
                    {percentage.toFixed(1)}%)
                  </span>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-cyan-400"
                    style={{
                      width: `${percentage}%`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <p className="mt-8 text-xs text-slate-500">
          {format(totalEncounters)} total encounters
          retrieved from Snowflake.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="text-lg font-semibold">
          Frequent Disorder-Labeled Concepts
        </h2>

        <p className="mt-1 text-sm text-slate-400">
          Synthetic FHIR Condition records · Live
        </p>

        <div className="mt-6 space-y-3">
          {data.diagnoses.map((item, index) => (
            <div
              key={item.name}
              className="flex items-center justify-between gap-4 rounded-xl bg-slate-800/60 p-4"
            >
              <div className="flex items-center gap-3">
                <span className="w-5 text-sm text-cyan-400">
                  {index + 1}
                </span>

                <span className="text-sm">
                  {item.name.replace(
                    /\s*\(disorder\)\s*$/i,
                    ""
                  )}
                </span>
              </div>

              <span className="text-sm font-medium">
                {format(item.records)}
              </span>
            </div>
          ))}
        </div>

        <p className="mt-5 text-xs leading-relaxed text-slate-500">
          Data retrieved from Snowflake Gold.
          Classification uses description labels,
          not validated clinical terminology groupings.
          Counts are not disease prevalence estimates.
        </p>
      </div>
    </section>
  );
}
