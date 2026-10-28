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

    const rows = await new Promise<Record<string, unknown>[]>(
      (resolve, reject) => {
        db.execute({
          sqlText: `
            SELECT
              CHECK_NAME,
              EXPECTED_COUNT,
              ACTUAL_COUNT,
              STATUS
            FROM CAREFLOW.GOLD.VW_WEB_QUALITY
            ORDER BY CHECK_NAME
          `,
          complete: (error, _statement, results) => {
            if (error) reject(error);
            else resolve(
              (results ?? []) as Record<string, unknown>[]
            );
          },
        });
      }
    );

    const checks = rows.map((row) => ({
      name: String(row.CHECK_NAME),
      expected: Number(row.EXPECTED_COUNT),
      actual: Number(row.ACTUAL_COUNT),
      status: String(row.STATUS),
    }));

    return Response.json(
      {
        total: checks.length,
        passed: checks.filter(
          (check) => check.status === "PASS"
        ).length,
        failed: checks.filter(
          (check) => check.status !== "PASS"
        ).length,
        checkedAt: new Date().toISOString(),
        checks,
      },
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (error) {
    console.error(
      "Snowflake quality query failed:",
      error instanceof Error ? error.message : "Unknown error"
    );

    return Response.json(
      { error: "Unable to retrieve data quality results" },
      { status: 500 }
    );
  } finally {
    if (connected) {
      db.destroy(() => {});
    }
  }
}
