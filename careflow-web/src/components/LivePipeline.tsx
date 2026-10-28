"use client";

import { useEffect, useState } from "react";

type PipelineRun = {
  id: string;
  startedAt: string | null;
  finishedAt: string | null;
  status: string;
  exitCode: number | null;
  durationSeconds: number | null;
  skippedFiles: number;
  uploadedFiles: number;
};

type FileActivity = {
  resource: string;
  outcome: string;
  count: number;
};

type PipelineData = {
  totalRuns: number;
  successfulRuns: number;
  failedRuns: number;
  latestRun: PipelineRun | null;
  runs: PipelineRun[];
  fileActivity: FileActivity[];
  checkedAt: string;
  historical: boolean;
};

function formatTimestamp(value: string | null) {
  if (!value) return "Unavailable";

  const match = value.match(
    /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})(?:\.\d+)? ([+-])(\d{2})(\d{2})$/
  );

  if (!match) return value;

  const [, date, time, sign, hours, minutes] = match;
  const zone =
    sign === "+" && hours === "00" && minutes === "00"
      ? "UTC"
      : `UTC${sign}${hours}:${minutes}`;

  return `${date} ${time} ${zone}`;
}

export default function LivePipeline() {
  const [data, setData] = useState<PipelineData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function loadPipeline() {
      try {
        const response = await fetch("/api/snowflake/pipeline", {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Pipeline API unavailable");
        }

        const result: PipelineData = await response.json();

        if (
          !Array.isArray(result.runs) ||
          !Array.isArray(result.fileActivity) ||
          !Number.isFinite(result.totalRuns) ||
          !Number.isFinite(result.successfulRuns) ||
          !Number.isFinite(result.failedRuns)
        ) {
          throw new Error("Invalid pipeline response");
        }

        if (!controller.signal.aborted) {
          setData(result);
        }
      } catch {
        if (!controller.signal.aborted) {
          setError(true);
        }
      }
    }

    void loadPipeline();

    return () => controller.abort();
  }, []);

  const fileEvents = data
    ? data.fileActivity.reduce(
        (total, item) => total + item.count, 0
      )
    : 0;

  return (
    <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">
            Pipeline Monitor
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Azure ingestion execution history
          </p>
        </div>

        <span className="rounded-full border border-slate-700 px-4 py-2 text-xs text-slate-300">
          Historical Audit Records
        </span>
      </div>

      {error && (
        <p className="mt-6 text-sm text-red-400" role="alert">
          Pipeline monitoring unavailable. Check server logs.
        </p>
      )}

      {!data && !error && (
        <p className="mt-6 text-sm text-slate-400" role="status">
          Loading pipeline history from Snowflake...
        </p>
      )}

      {data && (
        <>
          <div className="mt-7 grid grid-cols-2 gap-4 lg:grid-cols-4">
            {[
              ["Runs Shown", data.totalRuns],
              ["Successful", data.successfulRuns],
              ["Failed", data.failedRuns],
              ["File Events", fileEvents],
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

          {data.latestRun && (
            <div className="mt-6 rounded-xl border border-slate-700 bg-slate-800/40 p-5">
              <p className="text-xs uppercase tracking-wider text-slate-400">
                Latest Recorded Execution
              </p>

              <div className="mt-3 flex flex-wrap items-center gap-3">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    data.latestRun.status === "SUCCESS"
                      ? "bg-emerald-950 text-emerald-400"
                      : "bg-red-950 text-red-400"
                  }`}
                >
                  {data.latestRun.status}
                </span>

                <span className="font-mono text-sm text-slate-300">
                  {data.latestRun.id}
                </span>

                <span className="text-sm text-slate-400">
                  {formatTimestamp(data.latestRun.startedAt)}
                </span>
              </div>

              <p className="mt-3 text-xs text-slate-500">
                Latest recorded result, not a live
                pipeline-health indicator.
              </p>
            </div>
          )}

          <div className="mt-8">
            <h3 className="font-semibold">
              Execution History
            </h3>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-700 text-slate-400">
                  <tr>
                    <th className="py-3 pr-4">Run ID</th>
                    <th className="py-3 pr-4">Started</th>
                    <th className="py-3 pr-4">Status</th>
                    <th className="py-3 pr-4">Duration</th>
                    <th className="py-3 pr-4">Exit</th>
                    <th className="py-3 pr-4">Skipped</th>
                  </tr>
                </thead>

                <tbody>
                  {data.runs.map((run, index) => (
                    <tr
                      key={`${run.id}-${index}`}
                      className="border-b border-slate-800"
                    >
                      <td className="py-4 pr-4 font-mono text-xs">
                        {run.id}
                      </td>

                      <td className="py-4 pr-4 text-xs text-slate-400">
                        {formatTimestamp(run.startedAt)}
                      </td>

                      <td className={`py-4 pr-4 font-semibold ${
                        run.status === "SUCCESS"
                          ? "text-emerald-400"
                          : run.status === "FAILED"
                            ? "text-red-400"
                            : "text-amber-400"
                      }`}>
                        {run.status}
                      </td>

                      <td className="py-4 pr-4">
                        {run.durationSeconds === null
                          ? "—"
                          : `${run.durationSeconds.toFixed(2)}s`}
                      </td>

                      <td className="py-4 pr-4">
                        {run.exitCode ?? "—"}
                      </td>

                      <td className="py-4 pr-4">
                        {run.skippedFiles}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-8">
            <h3 className="font-semibold">
              File Activity
            </h3>

            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
              {data.fileActivity.map((item) => (
                <div
                  key={`${item.resource}-${item.outcome}`}
                  className="rounded-xl border border-slate-700 p-5"
                >
                  <p className="text-sm text-slate-300">
                    {item.resource}
                  </p>

                  <p className="mt-2 text-2xl font-semibold">
                    {item.count}
                  </p>

                  <p className="mt-1 text-xs text-slate-400">
                    {item.outcome} events
                  </p>
                </div>
              ))}
            </div>
          </div>

          <p className="mt-6 text-xs leading-relaxed text-slate-500">
            Historical ingestion records synchronized from
            local SQLite to Snowflake. These records do not
            represent live pipeline status or automatic
            synchronization. API queried at{" "}
            {new Date(data.checkedAt).toLocaleString()}.
          </p>
        </>
      )}
    </section>
  );
}
