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
            DATE_PART(
              'epoch_millisecond', CHECKED_AT
            ) AS CHECKED_AT_MS,

            DATE_PART(
              'epoch_millisecond',
              LAST_SUCCESSFUL_INGESTION
            ) AS LAST_SUCCESS_MS,

            DATE_PART(
              'epoch_millisecond',
              LAST_COMPLETED_INGESTION
            ) AS LAST_COMPLETED_MS,

            DATE_PART(
              'epoch_millisecond',
              LAST_AUDIT_RECORD_UPDATE
            ) AS LAST_AUDIT_UPDATE_MS,

            MINUTES_SINCE_SUCCESS,
            MINUTES_SINCE_AUDIT_UPDATE

          FROM CAREFLOW.GOLD.VW_WEB_FRESHNESS
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
      throw new Error("Freshness view returned no rows");
    }

    const numericOrNull = (value: unknown) =>
      value == null ? null : Number(value);

    return Response.json(
      {
        checkedAtMs: numericOrNull(row.CHECKED_AT_MS),
        lastSuccessfulIngestionMs:
          numericOrNull(row.LAST_SUCCESS_MS),
        lastCompletedIngestionMs:
          numericOrNull(row.LAST_COMPLETED_MS),
        lastAuditUpdateMs:
          numericOrNull(row.LAST_AUDIT_UPDATE_MS),
        minutesSinceSuccess:
          numericOrNull(row.MINUTES_SINCE_SUCCESS),
        minutesSinceAuditUpdate:
          numericOrNull(row.MINUTES_SINCE_AUDIT_UPDATE),
        monitoringType: "historical_ingestion_audit",
      },
      {
        headers: {
          "Cache-Control": "no-store",
        },
      }
    );
  } catch (error) {
    console.error(
      "Snowflake freshness query failed:",
      error instanceof Error
        ? error.message
        : "Unknown error"
    );

    return Response.json(
      { error: "Unable to retrieve freshness metrics" },
      { status: 500 }
    );
  } finally {
    if (connected) {
      db.destroy(() => {});
    }
  }
}
