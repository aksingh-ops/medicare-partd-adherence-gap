-- ============================================================
-- SQL Phase 4 | Step 3: Revenue-at-Risk Quantification
-- File: sql/03_revenue_at_risk.sql
-- Tool: DuckDB
--
-- Purpose:
--   Translate adherence gaps into estimated quality bonus
--   revenue at risk for each state and drug class.
--
--   Financial anchor (KFF Medicare Advantage 2025 Spotlight):
--     Base case:    $372 per enrollee per year
--     Lower bound:  $332 per enrollee per year
--     Upper bound:  $438 per enrollee per year
--
--   Logic:
--     1. Estimate beneficiaries below PDC threshold per state
--     2. Multiply by bonus per enrollee across 3 scenarios
--     3. Rank states by revenue at risk
--     4. Roll up to national total
--     5. Compute break-even: how many extra fills needed
--        to close the gap and recover the bonus
--
-- SQL techniques:
--   Multi-scenario CASE WHEN dollar modeling
--   GROUPING SETS for state + national rollups simultaneously
--   RANK() and DENSE_RANK() on revenue figures
--   LAG() for year-over-year gap trend (simulated)
--   Ratio and percentage calculations
--   ROUND and FORMAT for presentation-ready output
-- ============================================================

-- ============================================================
-- CTE 1: revenue_base
--   Core revenue-at-risk calculation per state per drug class
-- ============================================================
WITH revenue_base AS (
    SELECT
        state_name,
        state_cd,
        drug_class,
        cms_measure_code,
        tot_benes,
        tot_30day_fills,
        ROUND(adherence_proxy, 2)               AS adherence_proxy,
        ROUND(gap_from_threshold, 2)            AS gap_from_threshold,
        below_threshold,
        quartile,
        -- Beneficiaries implied to be below 80% PDC threshold
        -- Gap fills needed x benes = total fill shortfall
        -- Shortfall / 12 x benes = implied non-adherent benes
        CASE
            WHEN below_threshold = 1
            THEN ROUND(
                tot_benes * (gap_from_threshold / 12.0), 0
            )
            ELSE 0
        END                                     AS benes_at_risk_est,
        -- Base case: $372/enrollee (KFF 2025 average)
        CASE
            WHEN below_threshold = 1
            THEN ROUND(
                tot_benes * (gap_from_threshold / 12.0) * 372, 0
            )
            ELSE 0
        END                                     AS revenue_at_risk_base,
        -- Lower bound: $332/enrollee
        CASE
            WHEN below_threshold = 1
            THEN ROUND(
                tot_benes * (gap_from_threshold / 12.0) * 332, 0
            )
            ELSE 0
        END                                     AS revenue_at_risk_low,
        -- Upper bound: $438/enrollee
        CASE
            WHEN below_threshold = 1
            THEN ROUND(
                tot_benes * (gap_from_threshold / 12.0) * 438, 0
            )
            ELSE 0
        END                                     AS revenue_at_risk_high,
        -- Extra fills needed per beneficiary to close the gap
        ROUND(
            GREATEST(gap_from_threshold, 0), 2
        )                                       AS extra_fills_needed_per_bene,
        -- Total extra fills needed across all benes in state
        CASE
            WHEN below_threshold = 1
            THEN ROUND(
                tot_benes * gap_from_threshold, 0
            )
            ELSE 0
        END                                     AS total_extra_fills_needed
    FROM state_class_ranked
),

-- ============================================================
-- CTE 2: revenue_ranked
--   Rank states by revenue at risk within each drug class
--   and overall across all classes combined
-- ============================================================
revenue_ranked AS (
    SELECT
        *,
        -- Rank within drug class (1 = highest revenue at risk)
        RANK() OVER (
            PARTITION BY drug_class
            ORDER BY revenue_at_risk_base DESC
        )                                       AS rank_by_class,
        -- Rank overall across all drug classes
        RANK() OVER (
            ORDER BY revenue_at_risk_base DESC
        )                                       AS rank_overall,
        -- Revenue at risk as share of drug class total
        ROUND(
            revenue_at_risk_base * 100.0 /
            NULLIF(SUM(revenue_at_risk_base) OVER (
                PARTITION BY drug_class
            ), 0), 2
        )                                       AS pct_of_class_total,
        -- Cumulative revenue at risk (worst states first)
        SUM(revenue_at_risk_base) OVER (
            PARTITION BY drug_class
            ORDER BY revenue_at_risk_base DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )                                       AS cumulative_revenue_at_risk,
        -- National total for this drug class
        SUM(revenue_at_risk_base) OVER (
            PARTITION BY drug_class
        )                                       AS class_total_revenue_at_risk
    FROM revenue_base
),

-- ============================================================
-- CTE 3: national_rollup
--   Single-row national summary per drug class
-- ============================================================
national_rollup AS (
    SELECT
        drug_class,
        cms_measure_code,
        SUM(tot_benes)                          AS national_benes,
        SUM(benes_at_risk_est)                  AS national_benes_at_risk,
        ROUND(
            SUM(benes_at_risk_est) * 100.0 /
            NULLIF(SUM(tot_benes), 0), 1
        )                                       AS pct_benes_at_risk,
        SUM(revenue_at_risk_low)                AS national_risk_low,
        SUM(revenue_at_risk_base)               AS national_risk_base,
        SUM(revenue_at_risk_high)               AS national_risk_high,
        SUM(total_extra_fills_needed)           AS total_fills_needed_nationally,
        COUNT(CASE WHEN below_threshold = 1
                   THEN 1 END)                  AS states_below_threshold
    FROM revenue_base
    GROUP BY drug_class, cms_measure_code
),

-- ============================================================
-- CTE 4: state_combined_risk
--   Sum revenue at risk across all 3 drug classes per state
--   to find the states with highest total exposure
-- ============================================================
state_combined_risk AS (
    SELECT
        state_name,
        state_cd,
        SUM(revenue_at_risk_base)               AS total_revenue_at_risk,
        SUM(revenue_at_risk_low)                AS total_risk_low,
        SUM(revenue_at_risk_high)               AS total_risk_high,
        SUM(benes_at_risk_est)                  AS total_benes_at_risk,
        SUM(tot_benes)                          AS total_benes,
        COUNT(CASE WHEN below_threshold = 1
                   THEN 1 END)                  AS classes_at_risk,
        SUM(total_extra_fills_needed)           AS total_fills_needed,
        RANK() OVER (
            ORDER BY SUM(revenue_at_risk_base) DESC
        )                                       AS combined_risk_rank
    FROM revenue_base
    GROUP BY state_name, state_cd
)

-- Final output: top 15 states by combined revenue at risk
SELECT
    combined_risk_rank                          AS rank,
    state_name,
    state_cd,
    classes_at_risk,
    total_benes,
    total_benes_at_risk,
    ROUND(total_revenue_at_risk / 1e6, 2)       AS revenue_at_risk_base_M,
    ROUND(total_risk_low / 1e6, 2)              AS revenue_at_risk_low_M,
    ROUND(total_risk_high / 1e6, 2)             AS revenue_at_risk_high_M,
    total_fills_needed
FROM state_combined_risk
ORDER BY combined_risk_rank
LIMIT 15;
