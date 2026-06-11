-- ============================================================
-- SQL Phase 2 | Step 1: Data Load and Drug Class Mapping
-- File: sql/01_load_and_map.sql
-- Tool: DuckDB
-- Dataset: partd_geography_drug_2022.csv
--          CMS Medicare Part D Prescribers by Geography and Drug
--          CY2022 | 51 states + DC | 24 drug-class combinations
--
-- Purpose:
--   Load the CMS Part D dataset into DuckDB, validate schema,
--   and build the drug class mapping table that tags every
--   generic drug name into one of the three CMS Star Rating
--   triple-weighted adherence classes:
--     - diabetes       (CMS measure D08)
--     - ras_antagonist (CMS measure D09)
--     - statin         (CMS measure D10)
--
-- SQL techniques:
--   CREATE OR REPLACE TABLE, read_csv_auto,
--   CASE WHEN multi-condition mapping, GROUP BY validation,
--   NULL handling for suppressed CMS values
-- ============================================================

-- ============================================================
-- Step 1: Load raw CMS geography-drug data
-- ============================================================
CREATE OR REPLACE TABLE raw_partd AS
SELECT
    Prscrbr_Geo_Lvl,
    Prscrbr_Geo_Desc                    AS state_name,
    Prscrbr_Geo_Cd                      AS state_cd,
    Brnd_Name                           AS brand_name,
    Gnrc_Name                           AS generic_name,
    drug_class,
    CAST(Tot_Clms          AS INTEGER)  AS tot_clms,
    CAST(Tot_30day_Fills   AS INTEGER)  AS tot_30day_fills,
    CAST(Tot_Day_Suply     AS INTEGER)  AS tot_day_suply,
    CAST(Tot_Drug_Cst      AS DOUBLE)   AS tot_drug_cst,
    CAST(Tot_Benes         AS INTEGER)  AS tot_benes,
    CAST(GE65_Tot_Clms     AS INTEGER)  AS ge65_tot_clms,
    CAST(GE65_Tot_30day_Fills AS INTEGER) AS ge65_tot_30day_fills,
    CAST(GE65_Tot_Drug_Cst AS DOUBLE)   AS ge65_tot_drug_cst,
    CAST(GE65_Tot_Benes    AS INTEGER)  AS ge65_tot_benes
FROM read_csv_auto('data/partd_geography_drug_2022.csv');

-- Sanity check
SELECT
    COUNT(*)                            AS total_rows,
    COUNT(DISTINCT state_name)          AS unique_states,
    COUNT(DISTINCT generic_name)        AS unique_drugs,
    COUNT(DISTINCT drug_class)          AS drug_classes,
    SUM(tot_benes)                      AS total_beneficiaries,
    ROUND(SUM(tot_drug_cst)/1e9, 2)     AS total_drug_cost_billions
FROM raw_partd;

-- ============================================================
-- Step 2: Drug class mapping table
--   Explicitly maps each generic name to its CMS Star Rating
--   measure class. Uses the PQA/CMS official drug class
--   definitions for measures D08, D09, and D10.
--
--   In the real CMS dataset this mapping requires matching
--   against thousands of generic names using ILIKE pattern
--   matching. Here we use the drug_class field already
--   present, but the mapping logic below shows how it would
--   be built from a raw generic name field.
-- ============================================================
CREATE OR REPLACE TABLE drug_class_map AS
SELECT DISTINCT
    generic_name,
    brand_name,
    drug_class,
    -- CMS measure code for each class
    CASE drug_class
        WHEN 'diabetes'       THEN 'D08'
        WHEN 'ras_antagonist' THEN 'D09'
        WHEN 'statin'         THEN 'D10'
    END                                 AS cms_measure_code,
    -- Plain English measure name
    CASE drug_class
        WHEN 'diabetes'       THEN 'Medication Adherence for Diabetes Medications'
        WHEN 'ras_antagonist' THEN 'Medication Adherence for Hypertension (RAS Antagonists)'
        WHEN 'statin'         THEN 'Medication Adherence for Cholesterol (Statins)'
    END                                 AS cms_measure_name,
    -- Star Ratings weight (all three are triple-weighted)
    3                                   AS star_rating_weight
FROM raw_partd
ORDER BY drug_class, generic_name;

-- Verify mapping coverage
SELECT
    drug_class,
    cms_measure_code,
    COUNT(DISTINCT generic_name)        AS drugs_mapped,
    COUNT(DISTINCT brand_name)          AS brands_mapped
FROM drug_class_map
GROUP BY drug_class, cms_measure_code
ORDER BY drug_class;

-- ============================================================
-- Step 3: Clean working table
--   Joins raw data with drug class map, excludes suppressed
--   records (CMS suppresses counts < 11 — appear as NULL),
--   adds computed fields used downstream.
-- ============================================================
CREATE OR REPLACE TABLE partd_clean AS
SELECT
    r.state_name,
    r.state_cd,
    r.generic_name,
    r.brand_name,
    r.drug_class,
    m.cms_measure_code,
    m.cms_measure_name,
    m.star_rating_weight,
    -- Core metrics (exclude suppressed NULLs)
    COALESCE(r.tot_clms,         0)     AS tot_clms,
    COALESCE(r.tot_30day_fills,  0)     AS tot_30day_fills,
    COALESCE(r.tot_day_suply,    0)     AS tot_day_suply,
    COALESCE(r.tot_drug_cst,     0)     AS tot_drug_cst,
    COALESCE(r.tot_benes,        0)     AS tot_benes,
    -- 65+ subset
    COALESCE(r.ge65_tot_clms,    0)     AS ge65_tot_clms,
    COALESCE(r.ge65_tot_30day_fills, 0) AS ge65_tot_30day_fills,
    COALESCE(r.ge65_tot_drug_cst, 0)    AS ge65_tot_drug_cst,
    COALESCE(r.ge65_tot_benes,   0)     AS ge65_tot_benes,
    -- Adherence proxy: fills per beneficiary per year
    -- PDC-equivalent threshold = 9.6 (80% of 12 months)
    CASE
        WHEN COALESCE(r.tot_benes, 0) > 0
        THEN ROUND(
            CAST(r.tot_30day_fills AS DOUBLE) /
            NULLIF(r.tot_benes, 0), 4)
        ELSE NULL
    END                                 AS adherence_proxy,
    -- Gap from 9.6 threshold (positive = below threshold)
    CASE
        WHEN COALESCE(r.tot_benes, 0) > 0
        THEN ROUND(
            9.6 - (CAST(r.tot_30day_fills AS DOUBLE) /
            NULLIF(r.tot_benes, 0)), 4)
        ELSE NULL
    END                                 AS gap_from_threshold,
    -- Flag: is this drug-state combination below 80% PDC equivalent?
    CASE
        WHEN COALESCE(r.tot_benes, 0) > 0
         AND (CAST(r.tot_30day_fills AS DOUBLE) /
              NULLIF(r.tot_benes, 0)) < 9.6
        THEN 1
        ELSE 0
    END                                 AS below_threshold_flag
FROM raw_partd r
JOIN drug_class_map m
    ON r.generic_name = m.generic_name
-- Exclude suppressed rows (CMS suppresses benes < 11)
WHERE COALESCE(r.tot_benes, 0) >= 11
  AND COALESCE(r.tot_30day_fills, 0) > 0;

-- Final validation
SELECT
    drug_class,
    COUNT(*)                            AS rows,
    COUNT(DISTINCT state_name)          AS states,
    SUM(below_threshold_flag)           AS below_threshold_count,
    ROUND(AVG(adherence_proxy), 2)      AS avg_adherence_proxy,
    ROUND(MIN(adherence_proxy), 2)      AS min_proxy,
    ROUND(MAX(adherence_proxy), 2)      AS max_proxy
FROM partd_clean
GROUP BY drug_class
ORDER BY drug_class;
