{{ config(materialized='table') }}

SELECT
    RAW_RECORD:id::VARCHAR AS CONDITION_ID,

    REGEXP_SUBSTR(
        RAW_RECORD:subject:reference::VARCHAR,
        'Patient/([^/]+)$', 1, 1, 'e', 1
    ) AS PATIENT_ID,

    REGEXP_SUBSTR(
        RAW_RECORD:encounter:reference::VARCHAR,
        'Encounter/([^/]+)$', 1, 1, 'e', 1
    ) AS ENCOUNTER_ID,

    RAW_RECORD:code:coding[0]:system::VARCHAR AS CODE_SYSTEM,

    RAW_RECORD:code:coding[0]:code::VARCHAR AS DIAGNOSIS_CODE,

    RAW_RECORD:code:coding[0]:display::VARCHAR AS DIAGNOSIS_DESCRIPTION,

    RAW_RECORD:clinicalStatus:coding[0]:code::VARCHAR AS CLINICAL_STATUS,

    RAW_RECORD:verificationStatus:coding[0]:code::VARCHAR AS VERIFICATION_STATUS,

    SOURCE_FILE,
    SOURCE_ROW,
    INGESTED_AT

FROM {{ source('bronze', 'CONDITION_RAW') }}
