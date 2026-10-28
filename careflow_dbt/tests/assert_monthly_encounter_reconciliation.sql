WITH silver AS (
    SELECT COUNT(*) AS total_records
    FROM {{ ref('stg_encounters') }}
),

gold AS (
    SELECT COALESCE(
        SUM(TOTAL_ENCOUNTERS), 0
    ) AS total_records
    FROM {{ ref('fct_encounter_monthly') }}
)

SELECT
    silver.total_records AS silver_count,
    gold.total_records AS gold_count
FROM silver
CROSS JOIN gold
WHERE silver.total_records <> gold.total_records
