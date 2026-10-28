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
        if (error) {
          reject(error);
        } else {
          connected = true;
          resolve();
        }
      });
    });

    const rows = await new Promise<
      Record<string, unknown>[]
    >((resolve, reject) => {
      db.execute({
        sqlText: `
          SELECT
            LATEST_RUN_ID,
            LATEST_STATUS,
            LATEST_EXIT_CODE,
            TOTAL_COMPLETED_RUNS,
            TOTAL_FAILURES,
            FAILURES_SINCE_LAST_SUCCESS,
            EXECUTION_STATE,
            DATE_PART(
              'epoch_millisecond', CHECKED_AT
            ) AS CHECKED_AT_MS,
            DATE_PART(
              'epoch_millisecond', LATEST_FINISHED_AT
            ) AS LATEST_FINISHED_AT_MS
          FROM CAREFLOW.GOLD.VW_WEB_PIPELINE_HEALTH
          LIMIT 1
        `,
        complete: (error, _statement, result) => {
          if (error) {
            reject(error);
          } else {
            resolve(
              (result ?? []) as Record<string, unknown>[]
            );
          }
        },
      });
    });

    const row = rows[0];

    if (!row) {
      throw new Error("Pipeline Health view returned no rows");
    }

    function numberOrNull(value: unknown) {
      return value == null ? null : Number(value);
    }

    return Response.json(
      {
        latestRunId: row.LATEST_RUN_ID ?? null,
        latestStatus: row.LATEST_STATUS ?? null,
        latestExitCode: numberOrNull(
          row.LATEST_EXIT_CODE
        ),
        totalCompletedRuns: Number(
          row.TOTAL_COMPLETED_RUNS
        ),
        totalFailures: Number(row.TOTAL_FAILURES),
        failuresSinceLastSuccess: Number(
          row.FAILURES_SINCE_LAST_SUCCESS
        ),
        executionState: String(row.EXECUTION_STATE),
        checkedAtMs: numberOrNull(row.CHECKED_AT_MS),
        latestFinishedAtMs: numberOrNull(
          row.LATEST_FINISHED_AT_MS
        ),
        healthScope: "recorded_execution_history",
      },
      {
        headers: {
          "Cache-Control": "no-store",
        },
      }
    );
  } catch (error) {
    console.error(
      "Snowflake pipeline health query failed:",
      error instanceof Error
        ? error.message
        : "Unknown error"
    );

    return Response.json(
      { error: "Unable to retrieve pipeline health" },
      { status: 500 }
    );
  } finally {
    if (connected) {
      db.destroy(() => {});
    }
  }
}
