"use client";

import { useEffect, useState } from "react";

type FreshnessData = {
  checkedAtMs: number;
  lastSuccessfulIngestionMs: number | null;
  lastCompletedIngestionMs: number | null;
  lastAuditUpdateMs: number | null;
  minutesSinceSuccess: number | null;
  minutesSinceAuditUpdate: number | null;
  monitoringType: string;
};

function formatAge(minutes: number | null) {
  if (minutes === null || !Number.isFinite(minutes)) {
    return "No record";
  }

  const total = Math.max(0, Math.floor(minutes));

  if (total < 60) {
    return `${total} min`;
  }

  if (total < 1440) {
    return `${Math.floor(total / 60)}h ${total % 60}m`;
  }

  return `${Math.floor(total / 1440)}d ${Math.floor(
    (total % 1440) / 60
  )}h`;
}

function formatDate(timestamp: number | null) {
  if (timestamp === null || !Number.isFinite(timestamp)) {
    return "Unavailable";
  }

  return new Date(timestamp).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

export default function LiveFreshness() {
  const [data, setData] = useState<FreshnessData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshIndex, setRefreshIndex] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadFreshness() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch("/api/snowflake/freshness", {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("Freshness API unavailable");
        }

        const result =
          (await response.json()) as FreshnessData;

        if (
          !Number.isFinite(result.checkedAtMs) ||
          result.monitoringType !== "historical_ingestion_audit"
        ) {
          throw new Error("Invalid freshness response");
        }

        if (!controller.signal.aborted) {
          setData(result);
        }
      } catch {
        if (!controller.signal.aborted) {
          setError(
            "Unable to retrieve freshness measurements."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadFreshness();

    return () => controller.abort();
  }, [refreshIndex]);

  return (
    <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">
            Pipeline Freshness
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Recorded ingestion activity and audit updates
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
          Loading freshness measurements from Snowflake...
        </p>
      )}

      {data && (
        <>
          <div className="mt-7 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-xl bg-slate-800/60 p-5">
              <p className="text-sm text-slate-400">
                Since Last Successful Ingestion
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {formatAge(data.minutesSinceSuccess)}
              </p>
              <p className="mt-2 text-xs text-slate-500">
                At last Snowflake check
              </p>
            </div>

            <div className="rounded-xl bg-slate-800/60 p-5">
              <p className="text-sm text-slate-400">
                Since Last Audit Record Update
              </p>
              <p className="mt-3 text-3xl font-semibold text-white">
                {formatAge(data.minutesSinceAuditUpdate)}
              </p>
              <p className="mt-2 text-xs text-slate-500">
                At last Snowflake check
              </p>
            </div>
          </div>

          <div className="mt-6 rounded-xl border border-slate-700 p-5">
            <h3 className="text-sm font-semibold text-slate-200">
              Recorded Activity Timeline
            </h3>

            <dl className="mt-4 space-y-4 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <dt className="text-slate-400">
                  Last successful ingestion
                </dt>
                <dd className="font-medium text-slate-200">
                  {formatDate(data.lastSuccessfulIngestionMs)}
                </dd>
              </div>

              <div className="flex flex-wrap justify-between gap-2">
                <dt className="text-slate-400">
                  Last completed ingestion
                </dt>
                <dd className="font-medium text-slate-200">
                  {formatDate(data.lastCompletedIngestionMs)}
                </dd>
              </div>

              <div className="flex flex-wrap justify-between gap-2">
                <dt className="text-slate-400">
                  Last audit record update
                </dt>
                <dd className="font-medium text-slate-200">
                  {formatDate(data.lastAuditUpdateMs)}
                </dd>
              </div>

              <div className="border-t border-slate-700 pt-4">
                <div className="flex flex-wrap justify-between gap-2">
                  <dt className="text-slate-400">
                    Last Snowflake check
                  </dt>
                  <dd className="font-medium text-slate-200">
                    {formatDate(data.checkedAtMs)}
                  </dd>
                </div>
              </div>
            </dl>
          </div>

          <p className="mt-5 text-xs leading-relaxed text-slate-500">
            Measurements are snapshots taken when Snowflake
            is queried. Use Refresh to retrieve updated
            values. Successful ingestion may only verify
            previously uploaded files; it does not confirm
            that clinical data was refreshed or that a
            scheduled pipeline is healthy. Times are shown
            in your browser's local time zone.
          </p>
        </>
      )}
    </section>
  );
}
