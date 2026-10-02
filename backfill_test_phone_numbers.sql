BEGIN;

WITH source AS (
    SELECT national_id,
           regexp_replace(COALESCE(national_id,''),'[^0-9]','','g') AS id_digits
    FROM master_voters
    WHERE active AND NULLIF(BTRIM(phone),'') IS NULL
), candidates AS (
    SELECT national_id,'07' || id_digits AS generated_phone
    FROM source WHERE id_digits ~ '^[0-9]{7,8}$'
), occupied AS (
    SELECT CASE
        WHEN digits LIKE '254%' AND LENGTH(digits)=12 THEN '0' || SUBSTRING(digits FROM 4)
        WHEN LENGTH(digits)=9 THEN '0' || digits
        ELSE digits END AS normalized_phone
    FROM (
        SELECT regexp_replace(COALESCE(phone,''),'[^0-9]','','g') AS digits
        FROM master_voters
        WHERE active AND NULLIF(BTRIM(phone),'') IS NOT NULL
    ) existing
), safe AS (
    SELECT candidate.* FROM candidates candidate
    WHERE NOT EXISTS (
        SELECT 1 FROM occupied
        WHERE occupied.normalized_phone=candidate.generated_phone
    )
)
UPDATE master_voters voter
SET phone=safe.generated_phone,updated_at=NOW()
FROM safe
WHERE voter.active AND voter.national_id=safe.national_id
  AND NULLIF(BTRIM(voter.phone),'') IS NULL;

COMMIT;
