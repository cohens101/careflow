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

    const encounterRows = await query(`
      SELECT ENCOUNTER_CLASS, TOTAL_ENCOUNTERS
      FROM CAREFLOW.GOLD.VW_WEB_ENCOUNTERS
      ORDER BY TOTAL_ENCOUNTERS DESC
    `);

    const diagnosisRows = await query(`
      SELECT DIAGNOSIS_DESCRIPTION, CONDITION_RECORDS
      FROM CAREFLOW.GOLD.VW_WEB_DIAGNOSES
      ORDER BY CONDITION_RECORDS DESC,
               DIAGNOSIS_DESCRIPTION
      LIMIT 5
    `);

    return Response.json(
      {
        encounters: encounterRows.map((row) => ({
          category: String(row.ENCOUNTER_CLASS),
          count: Number(row.TOTAL_ENCOUNTERS),
        })),
        diagnoses: diagnosisRows.map((row) => ({
          name: String(row.DIAGNOSIS_DESCRIPTION),
          records: Number(row.CONDITION_RECORDS),
        })),
      },
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (error) {
    console.error(
      "Snowflake charts query failed:",
      error instanceof Error ? error.message : "Unknown error"
    );

    return Response.json(
      { error: "Unable to retrieve chart data" },
      { status: 500 }
    );
  } finally {
    if (connected) {
      db.destroy(() => {});
    }
  }
}
