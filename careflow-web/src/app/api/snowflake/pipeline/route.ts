import snowflake from "snowflake-sdk";
import { connection as requestTime } from "next/server";

export async function GET() {
  await requestTime();

  const account = process.env.SNOWFLAKE_ACCOUNT;
  const keyPath = process.env.SNOWFLAKE_PRIVATE_KEY_PATH;
  const passphrase =
    process.env.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE;

  if (!account || !keyPath || !passphrase) {
    return Response.json(
      { error: "Snowflake configuration unavailable" },
      { status: 500 }
    );
  }

  const db = snowflake.createConnection({
    account,
    username: "CAREFLOW_WEB_SVC",
    authenticator: "SNOWFLAKE_JWT",
    privateKeyPath: keyPath,
    privateKeyPass: passphrase,
    warehouse: "CAREFLOW_WH",
    database: "CAREFLOW",
    schema: "GOLD",
    role: "CAREFLOW_WEB_READ",
  });

  let connected = false;

  try {
    await new Promise<void>((resolve, reject) => {
      db.connect((error) => {
        if (error) reject(error);
        else {
          connected = true;
          resolve();
        }
      });
    });

    function query(sqlText: string) {
      return new Promise<Record<string, unknown>[]>(
        (resolve, reject) => {
          db.execute({
            sqlText,
            complete: (error, _statement, rows) => {
              if (error) reject(error);
              else resolve(
                (rows ?? []) as Record<string, unknown>[]
              );
            },
          });
        }
      );
    }

    const runRows = await query(`
      SELECT
        RUN_ID,
        STARTED_AT,
        FINISHED_AT,
        STATUS,
        EXIT_CODE,
        DURATION_SECONDS,
        SKIPPED_FILES,
        UPLOADED_FILES
      FROM CAREFLOW.GOLD.VW_WEB_PIPELINE_RUNS
      ORDER BY STARTED_AT DESC
      LIMIT 100
    `);

    const fileRows = await query(`
      SELECT RESOURCE, OUTCOME, EVENT_COUNT
      FROM CAREFLOW.GOLD.VW_WEB_PIPELINE_FILES
      ORDER BY RESOURCE, OUTCOME
    `);

    const runs = runRows.map((row) => ({
      id: String(row.RUN_ID),
      startedAt: row.STARTED_AT,
      finishedAt: row.FINISHED_AT,
      status: String(row.STATUS),
      exitCode: row.EXIT_CODE == null
        ? null
        : Number(row.EXIT_CODE),
      durationSeconds: row.DURATION_SECONDS == null
        ? null
        : Number(row.DURATION_SECONDS),
      skippedFiles: Number(row.SKIPPED_FILES),
      uploadedFiles: Number(row.UPLOADED_FILES),
    }));

    const fileActivity = fileRows.map((row) => ({
      resource: String(row.RESOURCE),
      outcome: String(row.OUTCOME),
      count: Number(row.EVENT_COUNT),
    }));

    return Response.json(
      {
        totalRuns: runs.length,
        successfulRuns: runs.filter(
          (r) => r.status === "SUCCESS"
        ).length,
        failedRuns: runs.filter(
          (r) => r.status === "FAILED"
        ).length,
        latestRun: runs[0] ?? null,
        runs,
        fileActivity,
        checkedAt: new Date().toISOString(),
        historical: true,
      },
      {
        headers: {
          "Cache-Control": "no-store",
        },
      }
    );
  } catch (error) {
    console.error(
      "Snowflake pipeline query failed:",
      error instanceof Error ? error.message : "Unknown error"
    );

    return Response.json(
      { error: "Unable to retrieve pipeline monitoring" },
      { status: 500 }
    );
  } finally {
    if (connected) {
      db.destroy(() => {});
    }
  }
}
