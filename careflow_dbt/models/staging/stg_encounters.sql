{{ config(materialized='table') }}

SELECT
    RAW_RECORD:id::VARCHAR AS ENCOUNTER_ID,

    REGEXP_SUBSTR(
        RAW_RECORD:subject:reference::VARCHAR,
        'Patient/([^/]+)$', 1, 1, 'e', 1
    ) AS PATIENT_ID,

    RAW_RECORD:status::VARCHAR AS ENCOUNTER_STATUS,

    RAW_RECORD:class:code::VARCHAR AS ENCOUNTER_CLASS,

    TRY_TO_TIMESTAMP_TZ(
        RAW_RECORD:period:start::VARCHAR
    ) AS ENCOUNTER_START,

    TRY_TO_TIMESTAMP_TZ(
        RAW_RECORD:period:end::VARCHAR
    ) AS ENCOUNTER_END,

    SOURCE_FILE,
    SOURCE_ROW,
    INGESTED_AT

FROM {{ source('bronze', 'ENCOUNTER_RAW') }}
