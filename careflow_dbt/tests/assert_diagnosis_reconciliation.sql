WITH silver AS (

    SELECT COUNT(*) AS total_conditions
    FROM {{ ref('stg_conditions') }}

),

gold AS (

    SELECT
        COALESCE(SUM(CONDITION_RECORDS), 0)
            AS total_conditions
    FROM {{ ref('fct_diagnosis_summary') }}

)

SELECT
    silver.total_conditions AS silver_count,
    gold.total_conditions AS gold_count

FROM silver
CROSS JOIN gold

WHERE silver.total_conditions <> gold.total_conditions
