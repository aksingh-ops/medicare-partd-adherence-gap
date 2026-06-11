-- ============================================================
-- SQL Phase 3 | Step 2: State-Level Adherence Proxy and Gap
-- File: sql/02_adherence_proxy.sql
-- Tool: DuckDB
--
-- Purpose:
--   Aggregate drug-level data to state + drug class level.
--   Compute the adherence proxy, gap from threshold, and
--   rank all 51 states for each of the three drug classes.
--
-- SQL techniques demonstrated:
--   Multi-step CTEs
--   RANK() / DENSE_RANK() / NTILE() / PERCENT_RANK()
--   Conditional aggregation with CASE WHEN
--   GROUPING SETS for national + state rollups
--   HAVING for threshold filtering
--   Window frames with PARTITION BY
-- ============================================================

-- ============================================================
-- CTE 1: state_class_totals
--   Roll up drug-level data to state + drug class level.
--   This is the primary analytical grain for all ranking.
-- ============================================================
WITH state_class_totals AS (
    SELECT
        state_name,
        state_cd,
        drug_class,
        cms_measure_code,
        cms_measure_name,
        -- Aggregate across all drugs within each class
        SUM(tot_benes)                          AS tot_benes,
        SUM(tot_30day_fills)                    AS tot_30day_fills,
        SUM(tot_clms)                           AS tot_clms,
        SUM(tot_day_suply)                      AS tot_day_suply,
        ROUND(SUM(tot_drug_cst), 2)             AS tot_drug_cst,
        SUM(ge65_tot_benes)                     AS ge65_benes,
        SUM(ge65_tot_30day_fills)               AS ge65_fills,
        COUNT(DISTINCT generic_name)            AS drugs_in_class,
        -- Class-level adherence proxy
        ROUND(
            CAST(SUM(tot_30day_fills) AS DOUBLE)
            / NULLIF(SUM(tot_benes), 0), 4
        )                                       AS adherence_proxy,
        -- Gap from 9.6 threshold (80% PDC equivalent)
        ROUND(
            9.6 - (
                CAST(SUM(tot_30day_fills) AS DOUBLE)
                / NULLIF(SUM(tot_benes), 0)
            ), 4
        )                                       AS gap_from_threshold,
        -- Below threshold flag
        CASE
            WHEN (CAST(SUM(tot_30day_fills) AS DOUBLE)
                  / NULLIF(SUM(tot_benes), 0)) < 9.6
            THEN 1 ELSE 0
        END                                     AS below_threshold
    FROM partd_clean
    GROUP BY
        state_name, state_cd,
        drug_class, cms_measure_code, cms_measure_name
),

-- ============================================================
-- CTE 2: state_class_ranked
--   Apply window functions to rank states within each
--   drug class from worst adherence to best.
-- ============================================================
state_class_ranked AS (
    SELECT
        *,
        -- Rank by adherence proxy (1 = worst adherence)
        RANK() OVER (
            PARTITION BY drug_class
            ORDER BY adherence_proxy ASC
        )                                       AS rank_worst_first,
        -- Rank by adherence proxy (1 = best adherence)
        RANK() OVER (
            PARTITION BY drug_class
            ORDER BY adherence_proxy DESC
        )                                       AS rank_best_first,
        -- Quartile: Q1 = worst 25%, Q4 = best 25%
        NTILE(4) OVER (
            PARTITION BY drug_class
            ORDER BY adherence_proxy ASC
        )                                       AS quartile,
        -- Percentile rank (0 = worst, 1 = best)
        ROUND(PERCENT_RANK() OVER (
            PARTITION BY drug_class
            ORDER BY adherence_proxy ASC
        ), 4)                                   AS pct_rank,
        -- National average for this drug class
        ROUND(AVG(adherence_proxy) OVER (
            PARTITION BY drug_class
        ), 4)                                   AS national_avg_proxy,
        -- Gap vs national average
        ROUND(
            adherence_proxy - AVG(adherence_proxy) OVER (
                PARTITION BY drug_class
            ), 4
        )                                       AS vs_national_avg,
        -- Running total of at-risk beneficiaries (worst to best)
        SUM(CASE WHEN below_threshold = 1
                 THEN tot_benes ELSE 0 END
        ) OVER (
            PARTITION BY drug_class
            ORDER BY adherence_proxy ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )                                       AS running_at_risk_benes
    FROM state_class_totals
),

-- ============================================================
-- CTE 3: threshold_summary
--   For each drug class: how many states are above/below
--   threshold, and total beneficiaries at risk?
-- ============================================================
threshold_summary AS (
    SELECT
        drug_class,
        cms_measure_code,
        COUNT(*)                                AS total_states,
        SUM(below_threshold)                    AS states_below_threshold,
        COUNT(*) - SUM(below_threshold)         AS states_above_threshold,
        ROUND(
            SUM(below_threshold) * 100.0 / COUNT(*), 1
        )                                       AS pct_states_below,
        SUM(CASE WHEN below_threshold = 1
                 THEN tot_benes ELSE 0 END)     AS benes_at_risk,
        SUM(tot_benes)                          AS total_benes,
        ROUND(
            SUM(CASE WHEN below_threshold = 1
                     THEN tot_benes ELSE 0 END)
            * 100.0 / NULLIF(SUM(tot_benes), 0), 1
        )                                       AS pct_benes_at_risk,
        ROUND(AVG(adherence_proxy), 2)          AS national_avg_proxy,
        ROUND(MIN(adherence_proxy), 2)          AS worst_state_proxy,
        ROUND(MAX(adherence_proxy), 2)          AS best_state_proxy
    FROM state_class_totals
    GROUP BY drug_class, cms_measure_code
)

-- ============================================================
-- Output A: Full state ranking table (all 51 states x 3 classes)
-- ============================================================
SELECT
    rank_worst_first                            AS rank,
    state_name,
    state_cd,
    drug_class,
    cms_measure_code,
    tot_benes,
    tot_30day_fills,
    ROUND(adherence_proxy, 2)                   AS adherence_proxy,
    ROUND(gap_from_threshold, 2)                AS gap_from_threshold,
    below_threshold,
    quartile,
    ROUND(pct_rank * 100, 1)                    AS pct_rank,
    ROUND(national_avg_proxy, 2)                AS national_avg,
    ROUND(vs_national_avg, 2)                   AS vs_national_avg
FROM state_class_ranked
ORDER BY drug_class, rank_worst_first;
