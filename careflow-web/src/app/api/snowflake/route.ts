import { connection } from "next/server";
import snowflake from "snowflake-sdk";



export async function GET() {
  await connection();
  try {
    const account = process.env.SNOWFLAKE_ACCOUNT;
    const keyPath = process.env.SNOWFLAKE_PRIVATE_KEY_PATH;
    const passphrase =
      process.env.SNOWFLAKE_PRIVATE_KEY_PASSPHRASE;

    if (!account || !keyPath || !passphrase) {
      throw new Error("Missing Snowflake server configuration");
    }

    const data = await new Promise<{
      patients: number;
      encounters: number;
      conditions: number;
    }>((resolve, reject) => {
      const connection = snowflake.createConnection({
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

      connection.connect((connectError) => {
        if (connectError) {
          reject(connectError);
          return;
        }

        connection.execute({
          sqlText: `
            SELECT
              TOTAL_PATIENTS,
              TOTAL_ENCOUNTERS,
              TOTAL_CONDITIONS
            FROM CAREFLOW.GOLD.VW_WEB_OVERVIEW
          `,
          complete: (queryError, _statement, rows) => {
            connection.destroy(() => {});

            if (queryError) {
              reject(queryError);
              return;
            }

            const row = rows?.[0];

            if (!row) {
              reject(new Error("No analytics data returned"));
              return;
            }

            resolve({
              patients: Number(row.TOTAL_PATIENTS),
              encounters: Number(row.TOTAL_ENCOUNTERS),
              conditions: Number(row.TOTAL_CONDITIONS),
            });
          },
        });
      });
    });

    return Response.json(data, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error(
      "Snowflake query failed:",
      error instanceof Error ? error.message : "Unknown error"
    );

    return Response.json(
      { error: "Unable to retrieve Snowflake analytics" },
      { status: 500 }
    );
  }
}
