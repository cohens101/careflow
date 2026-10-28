WITH source_counts AS (

    SELECT
        (SELECT COUNT(*)
         FROM {{ ref('stg_patients') }})
            AS EXPECTED_PATIENTS,

        (SELECT COUNT(*)
         FROM {{ ref('stg_encounters') }})
            AS EXPECTED_ENCOUNTERS

),

gold_counts AS (

    SELECT
        COUNT(*) AS ACTUAL_PATIENTS,
        COALESCE(SUM(TOTAL_ENCOUNTERS), 0)
            AS ACTUAL_ENCOUNTERS,

        COALESCE(SUM(
            AMBULATORY_ENCOUNTERS +
            EMERGENCY_ENCOUNTERS +
            INPATIENT_ENCOUNTERS +
            HOME_HEALTH_ENCOUNTERS +
            VIRTUAL_ENCOUNTERS +
            OTHER_ENCOUNTERS
        ), 0) AS CLASSIFIED_ENCOUNTERS

    FROM {{ ref('fct_patient_utilization') }}

)

SELECT *
FROM source_counts
CROSS JOIN gold_counts

WHERE EXPECTED_PATIENTS <> ACTUAL_PATIENTS
   OR EXPECTED_ENCOUNTERS <> ACTUAL_ENCOUNTERS
   OR ACTUAL_ENCOUNTERS <> CLASSIFIED_ENCOUNTERS
