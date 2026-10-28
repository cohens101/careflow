"use client";

import { useEffect, useState } from "react";

type HealthData = {
  latestRunId: string | null;
  latestStatus: string | null;
  latestExitCode: number | null;
  totalCompletedRuns: number;
  totalFailures: number;
  failuresSinceLastSuccess: number;
  executionState: string;
  checkedAtMs: number | null;
  latestFinishedAtMs: number | null;
  healthScope: string;
};

function formatDate(value: number | null) {
  if (value === null || !Number.isFinite(value)) {
    return "Unavailable";
  }

  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

export default function LiveHealth() {
  const [data, setData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshIndex, setRefreshIndex] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadHealth() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch("/api/snowflake/health", {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Pipeline Health API unavailable");
        }

        const result = (await response.json()) as HealthData;

        if (
          result.healthScope !== "recorded_execution_history" ||
          !Number.isFinite(result.totalCompletedRuns) ||
          !Number.isFinite(result.totalFailures) ||
          !Number.isFinite(result.failuresSinceLastSuccess) ||
          result.checkedAtMs === null ||
          !Number.isFinite(result.checkedAtMs)
        ) {
          throw new Error("Invalid health response");
        }

        if (!controller.signal.aborted) {
          setData(result);
        }
      } catch {
        if (!controller.signal.aborted) {
          setError("Unable to retrieve pipeline health.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadHealth();

    return () => controller.abort();
  }, [refreshIndex]);

  const succeeded =
    data?.executionState === "LATEST_RUN_SUCCEEDED";

  const attention =
    data?.executionState === "ATTENTION";

  const stateLabel = succeeded
    ? "Latest Run Succeeded"
    : attention
      ? "Recorded Failure Needs Attention"
      : data?.executionState === "NO_HISTORY"
        ? "No Execution History"
        : "Execution State Unknown";

  const stateStyle = succeeded
    ? "border-emerald-800 bg-emerald-950/50 text-emerald-400"
    : attention
      ? "border-red-800 bg-red-950/50 text-red-400"
      : "border-slate-700 bg-slate-800 text-slate-300";

  return (
    <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">
            Pipeline Health
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Recorded ingestion execution status
          </p>
        </div>

        <button
          type="button"
          disabled={loading}
          onClick={() => setRefreshIndex((value) => value + 1)}
          className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Checking..." : "Refresh"}
        </button>
      </div>

      {error && (
        <p className="mt-5 text-sm text-red-400" role="alert">
          {error}
          {data ? " Showing the previous snapshot." : ""}
        </p>
      )}

      {loading && !data && (
        <p className="mt-6 text-sm text-slate-400" role="status">
          Loading execution health from Snowflake...
        </p>
      )}

      {data && (
        <>
          <div className="mt-6">
            <span
              className={`inline-flex rounded-full border px-4 py-2 text-xs font-semibold ${stateStyle}`}
            >
              {stateLabel}
            </span>

            <p className="mt-3 text-xs text-slate-500">
              Status reflects recorded execution history,
              not continuous pipeline availability.
            </p>
          </div>

          <div className="mt-7 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl bg-slate-800/60 p-5">
              <p className="text-sm text-slate-400">
                Completed Runs
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {data.totalCompletedRuns}
              </p>
            </div>

            <div className="rounded-xl bg-slate-800/60 p-5">
              <p className="text-sm text-slate-400">
                Historical Failures
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {data.totalFailures}
              </p>
            </div>

            <div className="rounded-xl bg-slate-800/60 p-5">
              <p className="text-sm text-slate-400">
                Failures Since Last Success
              </p>
              <p
                className={`mt-3 text-3xl font-semibold ${
                  data.failuresSinceLastSuccess > 0
                    ? "text-red-400"
                    : "text-emerald-400"
                }`}
              >
                {data.failuresSinceLastSuccess}
              </p>
            </div>
          </div>

          <div className="mt-6 rounded-xl border border-slate-700 p-5">
            <h3 className="text-sm font-semibold text-slate-200">
              Latest Recorded Execution
            </h3>

            <dl className="mt-4 space-y-4 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <dt className="text-slate-400">Run ID</dt>
                <dd className="font-mono text-slate-200">
                  {data.latestRunId ?? "Unavailable"}
                </dd>
              </div>

              <div className="flex flex-wrap justify-between gap-2">
                <dt className="text-slate-400">Status</dt>
                <dd
                  className={
                    data.latestStatus === "SUCCESS"
                      ? "font-semibold text-emerald-400"
                      : data.latestStatus === "FAILED"
                        ? "font-semibold text-red-400"
                        : "font-semibold text-slate-300"
                  }
                >
                  {data.latestStatus ?? "Unavailable"}
                </dd>
              </div>

              <div className="flex flex-wrap justify-between gap-2">
                <dt className="text-slate-400">Exit code</dt>
                <dd className="text-slate-200">
                  {data.latestExitCode ?? "Unavailable"}
                </dd>
              </div>

              <div className="flex flex-wrap justify-between gap-2">
                <dt className="text-slate-400">
                  Completed at
                </dt>
                <dd className="text-slate-200">
                  {formatDate(data.latestFinishedAtMs)}
                </dd>
              </div>

              <div className="border-t border-slate-700 pt-4">
                <div className="flex flex-wrap justify-between gap-2">
                  <dt className="text-slate-400">
                    Last Snowflake check
                  </dt>
                  <dd className="text-slate-200">
                    {formatDate(data.checkedAtMs)}
                  </dd>
                </div>
              </div>
            </dl>
          </div>

          <p className="mt-5 text-xs leading-relaxed text-slate-500">
            Historical failures remain visible after recovery.
            A successful latest run does not establish data
            freshness, scheduling reliability, or continuous
            system health. Click Refresh to query Snowflake
            again. Times use your browser's local time zone.
          </p>
        </>
      )}
    </section>
  );
}
