"use client";

import { useEffect, useState } from "react";

type Check = {
  name: string;
  expected: number;
  actual: number;
  status: string;
};

type QualityData = {
  total: number;
  passed: number;
  failed: number;
  checkedAt: string;
  checks: Check[];
};

export default function LiveQuality() {
  const [data, setData] = useState<QualityData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/snowflake/quality", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error("API unavailable");
        return res.json();
      })
      .then((result: QualityData) => {
        if (
          !Array.isArray(result.checks) ||
          result.total !== result.checks.length
        ) {
          throw new Error("Invalid response");
        }
        if (!controller.signal.aborted) setData(result);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });

    return () => controller.abort();
  }, []);

  return (
    <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">
            Data Quality Monitor
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Live Bronze, Silver & Gold reconciliation
          </p>
        </div>

        {data && (
          <span className={`rounded-full px-4 py-2 text-sm ${
            data.failed === 0
              ? "bg-emerald-950 text-emerald-400"
              : "bg-red-950 text-red-400"
          }`}>
            {data.passed}/{data.total} Checks Passed
          </span>
        )}
      </div>

      {error && (
        <p className="mt-6 text-red-400">
          Quality monitoring unavailable.
        </p>
      )}

      {!data && !error && (
        <p className="mt-6 text-slate-400">
          Loading Snowflake quality results...
        </p>
      )}

      {data && (
        <>
          <div className="mt-7 grid grid-cols-3 gap-4">
            {[
              ["Total Checks", data.total],
              ["Passed", data.passed],
              ["Failed", data.failed],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl bg-slate-800/60 p-5"
              >
                <p className="text-sm text-slate-400">
                  {label}
                </p>
                <p className="mt-2 text-3xl font-semibold">
                  {value}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-700 text-slate-400">
                <tr>
                  <th className="py-3">Quality Check</th>
                  <th className="py-3">Expected</th>
                  <th className="py-3">Actual</th>
                  <th className="py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.checks.map((check) => (
                  <tr
                    key={check.name}
                    className="border-b border-slate-800"
                  >
                    <td className="py-4 pr-3">
                      {check.name}
                    </td>
                    <td className="py-4">
                      {check.expected.toLocaleString()}
                    </td>
                    <td className="py-4">
                      {check.actual.toLocaleString()}
                    </td>
                    <td className={`py-4 font-semibold ${
                      check.status === "PASS"
                        ? "text-emerald-400"
                        : "text-red-400"
                    }`}>
                      {check.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-5 text-xs text-slate-500">
            Checked {new Date(data.checkedAt).toLocaleString()}.
            Live count reconciliation; not a data freshness
            check or full dbt test history.
          </p>
        </>
      )}
    </section>
  );
}
