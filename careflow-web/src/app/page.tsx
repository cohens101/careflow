import LiveHealth from "@/components/LiveHealth";
import LiveFreshness from "@/components/LiveFreshness";
import LivePipeline from "@/components/LivePipeline";
import LiveQuality from "@/components/LiveQuality";
import LiveCharts from "@/components/LiveCharts";
import LiveMetrics from "@/components/LiveMetrics";



export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-6 py-8">

        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="text-2xl font-bold tracking-tight">
              Care<span className="text-cyan-400">Flow</span>
            </div>
            <p className="text-sm text-slate-400">
              Cloud Healthcare Data Platform
            </p>
          </div>
          <span className="rounded-full border border-amber-800 bg-amber-950/50 px-4 py-2 text-xs text-amber-300">
            Live Snowflake Analytics · Quality Test Snapshot
          </span>
        </header>

        <section className="py-10">
          <p className="mb-2 text-sm font-medium uppercase tracking-widest text-cyan-400">
            Analytics Overview
          </p>
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Healthcare Operations
          </h1>
          <p className="mt-3 text-slate-400">
            Synthetic clinical data processed through Azure,
            Snowflake, and dbt. Historical data through October 2026.
          </p>
        </section>

        <LiveMetrics />

        <LiveCharts />

        <LiveQuality />

        <LivePipeline />

        <LiveFreshness />

        <LiveHealth />

        <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="text-lg font-semibold">
            Data Platform Architecture
          </h2>
          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-4">
            {[
              ["01", "Azure Data Lake", "Source ingestion"],
              ["02", "Snowflake Bronze", "Original FHIR JSON"],
              ["03", "dbt Silver", "Structured clinical data"],
              ["04", "Snowflake Gold", "Business-ready analytics"],
            ].map(([number, title, description]) => (
              <div
                key={number}
                className="rounded-xl border border-slate-700 p-4"
              >
                <p className="text-xs text-cyan-400">{number}</p>
                <p className="mt-2 font-medium">{title}</p>
                <p className="mt-1 text-xs text-slate-400">
                  {description}
                </p>
              </div>
            ))}
          </div>
        </section>

        <footer className="mt-8 pb-6 text-xs text-slate-500">
          CareFlow · Portfolio demonstration · Synthetic healthcare data
        </footer>
      </div>
    </main>
  );
}
