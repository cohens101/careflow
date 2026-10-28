{{ config(materialized='table') }}

WITH source_data AS (

    SELECT
        RAW_RECORD,
        SOURCE_FILE,
        SOURCE_ROW,
        INGESTED_AT

    FROM {{ source('bronze', 'PATIENT_RAW') }}

)

SELECT
    RAW_RECORD:id::VARCHAR AS PATIENT_ID,

    RAW_RECORD:name[0]:given[0]::VARCHAR AS FIRST_NAME,

    RAW_RECORD:name[0]:family::VARCHAR AS LAST_NAME,

    RAW_RECORD:gender::VARCHAR AS GENDER,

    TRY_TO_DATE(
        RAW_RECORD:birthDate::VARCHAR
    ) AS BIRTH_DATE,

    RAW_RECORD:active::BOOLEAN AS ACTIVE,

    SOURCE_FILE,
    SOURCE_ROW,
    INGESTED_AT

FROM source_data
