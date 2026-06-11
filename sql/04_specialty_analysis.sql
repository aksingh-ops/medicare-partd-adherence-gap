-- ============================================================
-- SQL Phase 5 | Step 4: Prescriber Specialty Analysis
-- File: sql/04_specialty_analysis.sql
-- Tool: DuckDB
--
-- Purpose:
--   Identify which prescriber specialties are associated
--   with the lowest adherence proxy scores across the three
--   triple-weighted drug classes.
--
--   This answers the operational question:
--   "Which doctor types should our pharmacy outreach team
--    call first to improve patient adherence?"
--
--   A plan cannot call every prescriber. Specialty-level
--   ranking tells the outreach team where to concentrate
--   resources for maximum Star Rating impact per dollar spent.
--
-- Data note:
--   The CMS by-Provider-and-Drug dataset contains prescriber
--   specialty (Prscrbr_Type). We simulate this layer using
--   realistic specialty distributions matching CMS Part D
--   prescriber type data patterns.
--
-- SQL techniques:
--   CTE pipeline with specialty aggregation
--   RANK() and DENSE_RANK() within drug class partitions
--   CASE WHEN for specialty tier classification
--   LAG() for cross-specialty comparison
--   HAVING for minimum volume filtering
--   Weighted average adherence across specialties
-- ============================================================

-- ============================================================
-- Step 1: Build specialty-level adherence table
--   (In production: join to CMS by-Provider-and-Drug dataset
--    on Prscrbr_Type field. Here we use the specialty layer
--    built from the synthetic provider dataset.)
-- ============================================================
WITH specialty_totals AS (
    SELECT
        specialty,
        drug_class,
        cms_measure_code,
        SUM(tot_benes)                          AS tot_benes,
        SUM(tot_30day_fills)                    AS tot_30day_fills,
        SUM(tot_clms)                           AS tot_clms,
        COUNT(DISTINCT state_cd)                AS states_represented,
        -- Specialty-level adherence proxy
        ROUND(
            CAST(SUM(tot_30day_fills) AS DOUBLE)
            / NULLIF(SUM(tot_benes), 0), 4
        )                                       AS adherence_proxy,
        -- Gap from threshold
        ROUND(
            9.6 - (CAST(SUM(tot_30day_fills) AS DOUBLE)
            / NULLIF(SUM(tot_benes), 0)), 4
        )                                       AS gap_from_threshold,
        CASE
            WHEN (CAST(SUM(tot_30day_fills) AS DOUBLE)
                 / NULLIF(SUM(tot_benes), 0)) < 9.6
            THEN 1 ELSE 0
        END                                     AS below_threshold
    FROM specialty_adherence
    GROUP BY specialty, drug_class, cms_measure_code
    HAVING SUM(tot_benes) >= 1000    -- minimum volume filter
),

-- ============================================================
-- CTE 2: specialty_ranked
--   Rank specialties within each drug class
-- ============================================================
specialty_ranked AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY drug_class
            ORDER BY adherence_proxy ASC
        )                                       AS rank_worst_first,
        RANK() OVER (
            PARTITION BY drug_class
            ORDER BY adherence_proxy DESC
        )                                       AS rank_best_first,
        ROUND(AVG(adherence_proxy) OVER (
            PARTITION BY drug_class
        ), 4)                                   AS class_avg_proxy,
        ROUND(
            adherence_proxy - AVG(adherence_proxy) OVER (
                PARTITION BY drug_class
            ), 4
        )                                       AS vs_class_avg,
        -- Lag: difference from next-worst specialty
        ROUND(
            adherence_proxy - LAG(adherence_proxy) OVER (
                PARTITION BY drug_class
                ORDER BY adherence_proxy ASC
            ), 4
        )                                       AS gap_from_prev_specialty,
        -- Tier classification
        CASE
            WHEN RANK() OVER (
                PARTITION BY drug_class
                ORDER BY adherence_proxy ASC
            ) <= 3  THEN 'Priority 1 — Highest risk'
            WHEN RANK() OVER (
                PARTITION BY drug_class
                ORDER BY adherence_proxy ASC
            ) <= 6  THEN 'Priority 2 — Elevated risk'
            ELSE         'Priority 3 — Standard'
        END                                     AS outreach_priority
    FROM specialty_totals
),

-- ============================================================
-- CTE 3: specialty_combined_risk
--   Combined adherence proxy across all 3 drug classes
--   per specialty — for overall outreach priority ranking
-- ============================================================
specialty_combined_risk AS (
    SELECT
        specialty,
        COUNT(DISTINCT drug_class)              AS classes_tracked,
        ROUND(AVG(adherence_proxy), 3)          AS avg_proxy_all_classes,
        ROUND(AVG(gap_from_threshold), 3)       AS avg_gap_all_classes,
        SUM(tot_benes)                          AS total_benes,
        SUM(CASE WHEN below_threshold = 1
                 THEN tot_benes ELSE 0 END)     AS benes_at_risk,
        SUM(below_threshold)                    AS classes_below_threshold,
        RANK() OVER (
            ORDER BY AVG(adherence_proxy) ASC
        )                                       AS combined_priority_rank
    FROM specialty_totals
    GROUP BY specialty
)

-- Final output: combined specialty priority ranking
SELECT
    combined_priority_rank              AS priority_rank,
    specialty,
    classes_tracked,
    ROUND(avg_proxy_all_classes, 2)     AS avg_proxy,
    ROUND(avg_gap_all_classes, 2)       AS avg_gap,
    total_benes,
    benes_at_risk,
    classes_below_threshold,
    CASE
        WHEN combined_priority_rank <= 3
        THEN 'Priority 1 — Target immediately'
        WHEN combined_priority_rank <= 6
        THEN 'Priority 2 — Target next quarter'
        ELSE 'Priority 3 — Monitor'
    END                                 AS outreach_recommendation
FROM specialty_combined_risk
ORDER BY combined_priority_rank;
