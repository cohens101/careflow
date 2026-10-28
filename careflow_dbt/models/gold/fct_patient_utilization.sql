{{ config(materialized='table', schema='GOLD') }}

WITH patient_encounters AS (

    SELECT
        p.PATIENT_ID,
        p.GENDER,
        p.BIRTH_DATE,
        e.ENCOUNTER_ID,
        e.ENCOUNTER_CLASS,
        e.ENCOUNTER_START

    FROM {{ ref('stg_patients') }} p

    LEFT JOIN {{ ref('stg_encounters') }} e
        ON p.PATIENT_ID = e.PATIENT_ID

)

SELECT
    PATIENT_ID,
    GENDER,
    BIRTH_DATE,

    COUNT(ENCOUNTER_ID) AS TOTAL_ENCOUNTERS,

    SUM(IFF(ENCOUNTER_CLASS = 'AMB', 1, 0))
        AS AMBULATORY_ENCOUNTERS,

    SUM(IFF(ENCOUNTER_CLASS = 'EMER', 1, 0))
        AS EMERGENCY_ENCOUNTERS,

    SUM(IFF(ENCOUNTER_CLASS = 'IMP', 1, 0))
        AS INPATIENT_ENCOUNTERS,

    SUM(IFF(ENCOUNTER_CLASS = 'HH', 1, 0))
        AS HOME_HEALTH_ENCOUNTERS,

    SUM(IFF(ENCOUNTER_CLASS = 'VR', 1, 0))
        AS VIRTUAL_ENCOUNTERS,

    SUM(IFF(
        ENCOUNTER_ID IS NOT NULL
        AND (
            ENCOUNTER_CLASS IS NULL
            OR ENCOUNTER_CLASS NOT IN (
                'AMB', 'EMER', 'IMP', 'HH', 'VR'
            )
        ),
        1, 0
    )) AS OTHER_ENCOUNTERS,

    MIN(ENCOUNTER_START) AS FIRST_ENCOUNTER,
    MAX(ENCOUNTER_START) AS LAST_ENCOUNTER

FROM patient_encounters

GROUP BY
    PATIENT_ID,
    GENDER,
    BIRTH_DATE
