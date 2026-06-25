"""
run_pipeline.py
---------------
Complete pipeline for Medicare Part D Adherence Gap Analysis.

Run with one command:
    python run_pipeline.py

What this does:
    1. Generates synthetic CMS Part D dataset if real data not present
    2. Runs all SQL analysis phases via DuckDB
    3. Generates all charts and saves to reports/
    4. Saves all CSV outputs to reports/

Real CMS data (optional):
    Download from: https://data.cms.gov/provider-summary-by-type-of-service/
    medicare-part-d-prescribers/medicare-part-d-prescribers-by-geography-and-drug
    Place as: data/partd_geography_drug_2022.csv
    The pipeline will use real data if present, synthetic data otherwise.
"""

import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
import os
import sys

np.random.seed(42)

# -------------------------------------------------------
# Setup directories
# -------------------------------------------------------
os.makedirs('data',    exist_ok=True)
os.makedirs('reports', exist_ok=True)

DATA_FILE = 'data/partd_geography_drug_2022.csv'
DB_FILE   = 'data/partd.duckdb'

print("=" * 60)
print("Medicare Part D Adherence Gap Analysis Pipeline")
print("=" * 60)

# -------------------------------------------------------
# STEP 1: Generate synthetic dataset if real data absent
# -------------------------------------------------------
if not os.path.exists(DATA_FILE):
    print("\n[Step 1] Real CMS data not found.")
    print("         Generating synthetic dataset matching CMS schema...")

    states = [
        ('Alabama','AL'),('Alaska','AK'),('Arizona','AZ'),('Arkansas','AR'),
        ('California','CA'),('Colorado','CO'),('Connecticut','CT'),('Delaware','DE'),
        ('Florida','FL'),('Georgia','GA'),('Hawaii','HI'),('Idaho','ID'),
        ('Illinois','IL'),('Indiana','IN'),('Iowa','IA'),('Kansas','KS'),
        ('Kentucky','KY'),('Louisiana','LA'),('Maine','ME'),('Maryland','MD'),
        ('Massachusetts','MA'),('Michigan','MI'),('Minnesota','MN'),('Mississippi','MS'),
        ('Missouri','MO'),('Montana','MT'),('Nebraska','NE'),('Nevada','NV'),
        ('New Hampshire','NH'),('New Jersey','NJ'),('New Mexico','NM'),('New York','NY'),
        ('North Carolina','NC'),('North Dakota','ND'),('Ohio','OH'),('Oklahoma','OK'),
        ('Oregon','OR'),('Pennsylvania','PA'),('Rhode Island','RI'),('South Carolina','SC'),
        ('South Dakota','SD'),('Tennessee','TN'),('Texas','TX'),('Utah','UT'),
        ('Vermont','VT'),('Virginia','VA'),('Washington','WA'),('West Virginia','WV'),
        ('Wisconsin','WI'),('Wyoming','WY'),('District of Columbia','DC'),
    ]

    drugs = {
        'diabetes': [
            ('metformin hydrochloride','Glucophage',0.95,0.08),
            ('sitagliptin phosphate','Januvia',0.72,0.12),
            ('empagliflozin','Jardiance',0.68,0.14),
            ('liraglutide','Victoza',0.61,0.15),
            ('glipizide','Glucotrol',0.88,0.09),
            ('pioglitazone hydrochloride','Actos',0.78,0.11),
            ('dulaglutide','Trulicity',0.65,0.13),
            ('semaglutide','Ozempic',0.58,0.16),
        ],
        'ras_antagonist': [
            ('lisinopril','Zestril',0.92,0.07),
            ('losartan potassium','Cozaar',0.89,0.08),
            ('amlodipine besylate-benazepril','Lotrel',0.82,0.09),
            ('ramipril','Altace',0.85,0.08),
            ('valsartan','Diovan',0.80,0.10),
            ('olmesartan medoxomil','Benicar',0.77,0.11),
            ('enalapril maleate','Vasotec',0.83,0.09),
            ('irbesartan','Avapro',0.76,0.11),
        ],
        'statin': [
            ('atorvastatin calcium','Lipitor',0.93,0.07),
            ('rosuvastatin calcium','Crestor',0.88,0.09),
            ('simvastatin','Zocor',0.87,0.08),
            ('pravastatin sodium','Pravachol',0.81,0.10),
            ('lovastatin','Mevacor',0.79,0.11),
            ('fluvastatin sodium','Lescol',0.72,0.12),
            ('pitavastatin calcium','Livalo',0.69,0.13),
            ('ezetimibe-simvastatin','Vytorin',0.75,0.11),
        ],
    }

    state_modifiers = {
        'AL':-0.08,'MS':-0.09,'LA':-0.07,'AR':-0.06,'WV':-0.07,
        'TN':-0.05,'KY':-0.06,'OK':-0.04,'SC':-0.05,'GA':-0.04,
        'TX':-0.03,'NM':-0.04,'NV':-0.03,'AK':-0.02,'MT':-0.02,
        'MA': 0.06,'CT': 0.05,'RI': 0.04,'MN': 0.05,'VT': 0.04,
        'NH': 0.04,'WI': 0.03,'IA': 0.03,'ND': 0.03,'SD': 0.02,
        'NY': 0.02,'NJ': 0.02,'WA': 0.02,'OR': 0.01,'CO': 0.01,
    }

    pop_tiers = {
        'CA':850000,'TX':720000,'FL':680000,'NY':580000,'PA':440000,
        'OH':390000,'IL':370000,'MI':340000,'NC':310000,'GA':290000,
        'NJ':270000,'VA':260000,'WA':240000,'AZ':230000,'MA':225000,
        'TN':210000,'IN':205000,'MO':200000,'MD':190000,'WI':185000,
        'MN':180000,'CO':170000,'AL':165000,'SC':160000,'LA':155000,
        'KY':152000,'OR':148000,'OK':145000,'CT':140000,'IA':130000,
        'MS':125000,'AR':120000,'KS':115000,'UT':110000,'NV':108000,
        'NM':95000,'NE':90000,'WV':88000,'ID':85000,'HI':82000,
        'ME':80000,'NH':78000,'RI':72000,'MT':68000,'DE':65000,
        'SD':62000,'ND':60000,'AK':48000,'VT':45000,'WY':42000,
        'DC':38000,
    }

    rows = []
    for state_name, state_abbr in states:
        mod = state_modifiers.get(state_abbr, 0)
        base_benes = pop_tiers.get(state_abbr, 100000)
        for drug_class, drug_list in drugs.items():
            for gnrc_name, brnd_name, base_adh, std_dev in drug_list:
                drug_share = np.random.uniform(0.08, 0.25)
                tot_benes  = max(11, int(base_benes * drug_share *
                                np.random.uniform(0.85, 1.15)))
                adh = np.clip(base_adh + mod +
                              np.random.normal(0, std_dev), 0.45, 0.99)
                fills_per_bene = adh * 12
                tot_30day_fills = int(tot_benes * fills_per_bene)
                tot_clms = int(tot_30day_fills * np.random.uniform(1.05, 1.15))
                tot_day_suply = int(tot_30day_fills * 30 *
                                    np.random.uniform(0.97, 1.03))
                if drug_class == 'diabetes':
                    cost_per_claim = np.random.uniform(25, 280)
                elif drug_class == 'ras_antagonist':
                    cost_per_claim = np.random.uniform(12, 85)
                else:
                    cost_per_claim = np.random.uniform(10, 120)
                tot_drug_cst = round(tot_clms * cost_per_claim, 2)
                ge65_ratio = np.random.uniform(0.70, 0.82)
                ge65_benes = max(11, int(tot_benes * ge65_ratio))
                ge65_clms  = int(tot_clms * ge65_ratio *
                                  np.random.uniform(0.95, 1.05))
                ge65_fills = int(tot_30day_fills * ge65_ratio)
                ge65_cost  = round(tot_drug_cst * ge65_ratio, 2)
                rows.append({
                    'Prscrbr_Geo_Lvl':     'State',
                    'Prscrbr_Geo_Desc':     state_name,
                    'Prscrbr_Geo_Cd':       state_abbr,
                    'Brnd_Name':            brnd_name,
                    'Gnrc_Name':            gnrc_name,
                    'drug_class':           drug_class,
                    'Tot_Clms':             tot_clms,
                    'Tot_30day_Fills':      tot_30day_fills,
                    'Tot_Day_Suply':        tot_day_suply,
                    'Tot_Drug_Cst':         tot_drug_cst,
                    'Tot_Benes':            tot_benes,
                    'GE65_Tot_Clms':        ge65_clms,
                    'GE65_Tot_30day_Fills': ge65_fills,
                    'GE65_Tot_Drug_Cst':    ge65_cost,
                    'GE65_Tot_Benes':       ge65_benes,
                })

    df_syn = pd.DataFrame(rows)
    df_syn.to_csv(DATA_FILE, index=False)
    print(f"         Synthetic dataset created: {len(df_syn):,} rows, "
          f"{df_syn['Prscrbr_Geo_Desc'].nunique()} states")
else:
    print(f"\n[Step 1] Real CMS data found: {DATA_FILE}")
    df_check = pd.read_csv(DATA_FILE, nrows=5)
    print(f"         Columns: {df_check.columns.tolist()}")

# -------------------------------------------------------
# STEP 2: Load data and map drug classes (Phase 2 SQL)
# -------------------------------------------------------
print("\n[Step 2] Loading data and mapping drug classes...")
con = duckdb.connect(DB_FILE)

con.execute(f"""
CREATE OR REPLACE TABLE raw_partd AS
SELECT
    Prscrbr_Geo_Desc AS state_name,
    Prscrbr_Geo_Cd   AS state_cd,
    Brnd_Name        AS brand_name,
    Gnrc_Name        AS generic_name,
    drug_class,
    CAST(Tot_Clms             AS INTEGER) AS tot_clms,
    CAST(Tot_30day_Fills      AS INTEGER) AS tot_30day_fills,
    CAST(Tot_Day_Suply        AS INTEGER) AS tot_day_suply,
    CAST(Tot_Drug_Cst         AS DOUBLE)  AS tot_drug_cst,
    CAST(Tot_Benes            AS INTEGER) AS tot_benes,
    CAST(GE65_Tot_Clms        AS INTEGER) AS ge65_tot_clms,
    CAST(GE65_Tot_30day_Fills AS INTEGER) AS ge65_tot_30day_fills,
    CAST(GE65_Tot_Drug_Cst    AS DOUBLE)  AS ge65_tot_drug_cst,
    CAST(GE65_Tot_Benes       AS INTEGER) AS ge65_tot_benes
FROM read_csv_auto('{DATA_FILE}')
""")

overview = con.execute("""
    SELECT COUNT(*) AS rows,
           COUNT(DISTINCT state_name) AS states,
           COUNT(DISTINCT generic_name) AS drugs,
           SUM(tot_benes) AS total_benes,
           ROUND(SUM(tot_drug_cst)/1e9,2) AS total_cost_billions
    FROM raw_partd
""").df()
print(f"  Loaded: {overview.to_string(index=False)}")

con.execute("""
CREATE OR REPLACE TABLE drug_class_map AS
SELECT DISTINCT generic_name, brand_name, drug_class,
    CASE drug_class
        WHEN 'diabetes'       THEN 'D08'
        WHEN 'ras_antagonist' THEN 'D09'
        WHEN 'statin'         THEN 'D10'
    END AS cms_measure_code,
    CASE drug_class
        WHEN 'diabetes'
            THEN 'Medication Adherence for Diabetes Medications'
        WHEN 'ras_antagonist'
            THEN 'Medication Adherence for Hypertension (RAS Antagonists)'
        WHEN 'statin'
            THEN 'Medication Adherence for Cholesterol (Statins)'
    END AS cms_measure_name,
    3 AS star_rating_weight
FROM raw_partd
ORDER BY drug_class, generic_name
""")

con.execute("""
CREATE OR REPLACE TABLE partd_clean AS
SELECT
    r.state_name, r.state_cd,
    r.generic_name, r.brand_name,
    r.drug_class, m.cms_measure_code, m.cms_measure_name,
    m.star_rating_weight,
    COALESCE(r.tot_clms, 0)             AS tot_clms,
    COALESCE(r.tot_30day_fills, 0)      AS tot_30day_fills,
    COALESCE(r.tot_day_suply, 0)        AS tot_day_suply,
    COALESCE(r.tot_drug_cst, 0)         AS tot_drug_cst,
    COALESCE(r.tot_benes, 0)            AS tot_benes,
    COALESCE(r.ge65_tot_benes, 0)       AS ge65_tot_benes,
    COALESCE(r.ge65_tot_30day_fills, 0) AS ge65_tot_30day_fills,
    CASE WHEN COALESCE(r.tot_benes, 0) > 0
         THEN ROUND(CAST(r.tot_30day_fills AS DOUBLE)
                    / NULLIF(r.tot_benes, 0), 4)
         ELSE NULL END                  AS adherence_proxy,
    CASE WHEN COALESCE(r.tot_benes, 0) > 0
         THEN ROUND(9.6 - (CAST(r.tot_30day_fills AS DOUBLE)
                            / NULLIF(r.tot_benes, 0)), 4)
         ELSE NULL END                  AS gap_from_threshold,
    CASE WHEN COALESCE(r.tot_benes, 0) > 0
          AND (CAST(r.tot_30day_fills AS DOUBLE)
               / NULLIF(r.tot_benes, 0)) < 9.6
         THEN 1 ELSE 0 END              AS below_threshold_flag
FROM raw_partd r
JOIN drug_class_map m ON r.generic_name = m.generic_name
WHERE COALESCE(r.tot_benes, 0) >= 11
  AND COALESCE(r.tot_30day_fills, 0) > 0
""")
print("  Drug class mapping complete.")

# -------------------------------------------------------
# STEP 3: State adherence ranking (Phase 3 SQL)
# -------------------------------------------------------
print("\n[Step 3] Building state adherence rankings...")
con.execute("""
CREATE OR REPLACE TABLE state_class_ranked AS
WITH state_class_totals AS (
    SELECT
        state_name, state_cd, drug_class,
        cms_measure_code, cms_measure_name,
        SUM(tot_benes)          AS tot_benes,
        SUM(tot_30day_fills)    AS tot_30day_fills,
        SUM(tot_clms)           AS tot_clms,
        SUM(tot_drug_cst)       AS tot_drug_cst,
        SUM(ge65_tot_benes)     AS ge65_benes,
        SUM(ge65_tot_30day_fills) AS ge65_fills,
        COUNT(DISTINCT generic_name) AS drugs_in_class,
        ROUND(CAST(SUM(tot_30day_fills) AS DOUBLE)
              / NULLIF(SUM(tot_benes), 0), 4) AS adherence_proxy,
        ROUND(9.6 - (CAST(SUM(tot_30day_fills) AS DOUBLE)
              / NULLIF(SUM(tot_benes), 0)), 4) AS gap_from_threshold,
        CASE WHEN (CAST(SUM(tot_30day_fills) AS DOUBLE)
                   / NULLIF(SUM(tot_benes), 0)) < 9.6
             THEN 1 ELSE 0 END AS below_threshold
    FROM partd_clean
    GROUP BY state_name, state_cd, drug_class,
             cms_measure_code, cms_measure_name
)
SELECT *,
    RANK() OVER (PARTITION BY drug_class
                 ORDER BY adherence_proxy ASC)  AS rank_worst_first,
    RANK() OVER (PARTITION BY drug_class
                 ORDER BY adherence_proxy DESC) AS rank_best_first,
    NTILE(4) OVER (PARTITION BY drug_class
                   ORDER BY adherence_proxy ASC) AS quartile,
    ROUND(PERCENT_RANK() OVER (
        PARTITION BY drug_class
        ORDER BY adherence_proxy ASC), 4)        AS pct_rank,
    ROUND(AVG(adherence_proxy) OVER (
        PARTITION BY drug_class), 4)             AS national_avg_proxy,
    ROUND(adherence_proxy - AVG(adherence_proxy) OVER (
        PARTITION BY drug_class), 4)             AS vs_national_avg,
    SUM(CASE WHEN below_threshold = 1
             THEN tot_benes ELSE 0 END)
        OVER (PARTITION BY drug_class
              ORDER BY adherence_proxy ASC
              ROWS BETWEEN UNBOUNDED PRECEDING
                       AND CURRENT ROW)          AS running_at_risk_benes
FROM state_class_totals
""")

result = con.execute("""
    SELECT drug_class,
           SUM(below_threshold) AS below_threshold,
           COUNT(*) AS total_states
    FROM state_class_ranked
    GROUP BY drug_class
    ORDER BY drug_class
""").df()
print(f"  State rankings built:\n{result.to_string(index=False)}")

con.execute("""
    COPY (
        SELECT rank_worst_first AS rank, state_name, state_cd,
               drug_class, cms_measure_code, tot_benes,
               ROUND(adherence_proxy, 2)      AS adherence_proxy,
               ROUND(gap_from_threshold, 2)   AS gap_from_threshold,
               below_threshold, quartile,
               ROUND(national_avg_proxy, 2)   AS national_avg
        FROM state_class_ranked
        ORDER BY drug_class, rank_worst_first
    ) TO 'reports/state_adherence_ranking.csv' (HEADER, DELIMITER ',')
""")
print("  Saved: reports/state_adherence_ranking.csv")

# -------------------------------------------------------
# STEP 4: Revenue at risk (Phase 4 SQL)
# -------------------------------------------------------
print("\n[Step 4] Quantifying revenue at risk...")
con.execute("""
CREATE OR REPLACE TABLE revenue_at_risk AS
WITH rb AS (
    SELECT
        state_name, state_cd, drug_class, cms_measure_code,
        tot_benes, tot_30day_fills,
        ROUND(adherence_proxy, 2)      AS adherence_proxy,
        ROUND(gap_from_threshold, 2)   AS gap_from_threshold,
        below_threshold, quartile,
        CASE WHEN below_threshold = 1
             THEN ROUND(tot_benes * (gap_from_threshold / 12.0), 0)
             ELSE 0 END AS benes_at_risk_est,
        CASE WHEN below_threshold = 1
             THEN ROUND(tot_benes * (gap_from_threshold / 12.0) * 372, 0)
             ELSE 0 END AS revenue_at_risk_base,
        CASE WHEN below_threshold = 1
             THEN ROUND(tot_benes * (gap_from_threshold / 12.0) * 332, 0)
             ELSE 0 END AS revenue_at_risk_low,
        CASE WHEN below_threshold = 1
             THEN ROUND(tot_benes * (gap_from_threshold / 12.0) * 438, 0)
             ELSE 0 END AS revenue_at_risk_high,
        ROUND(GREATEST(gap_from_threshold, 0), 2) AS extra_fills_needed_per_bene,
        CASE WHEN below_threshold = 1
             THEN ROUND(tot_benes * gap_from_threshold, 0)
             ELSE 0 END AS total_extra_fills_needed
    FROM state_class_ranked
)
SELECT *,
    RANK() OVER (
        PARTITION BY drug_class
        ORDER BY revenue_at_risk_base DESC) AS rank_by_class,
    ROUND(revenue_at_risk_base * 100.0 /
          NULLIF(SUM(revenue_at_risk_base) OVER (
              PARTITION BY drug_class), 0), 2) AS pct_of_class_total,
    SUM(revenue_at_risk_base) OVER (
        PARTITION BY drug_class
        ORDER BY revenue_at_risk_base DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_revenue_at_risk
FROM rb
""")

total_risk = con.execute("""
    SELECT ROUND(SUM(revenue_at_risk_base) / 1e6, 1) AS total_M
    FROM revenue_at_risk
""").fetchone()[0]
print(f"  Total national revenue at risk: ${total_risk}M")

con.execute("""
    COPY (
        SELECT rank_by_class AS rank, state_name, state_cd,
               drug_class, cms_measure_code, tot_benes,
               benes_at_risk_est,
               revenue_at_risk_low, revenue_at_risk_base,
               revenue_at_risk_high,
               extra_fills_needed_per_bene,
               total_extra_fills_needed, pct_of_class_total
        FROM revenue_at_risk
        WHERE below_threshold = 1
        ORDER BY drug_class, rank_by_class
    ) TO 'reports/revenue_at_risk_by_state.csv' (HEADER, DELIMITER ',')
""")

con.execute("""
    COPY (
        SELECT
            RANK() OVER (
                ORDER BY SUM(revenue_at_risk_base) DESC) AS rank,
            state_name, state_cd,
            COUNT(CASE WHEN below_threshold = 1
                       THEN 1 END)                AS classes_at_risk,
            SUM(tot_benes)                        AS total_benes,
            SUM(benes_at_risk_est)                AS benes_at_risk,
            ROUND(SUM(revenue_at_risk_base)/1e6,2) AS risk_base_M,
            ROUND(SUM(revenue_at_risk_low)/1e6,2)  AS risk_low_M,
            ROUND(SUM(revenue_at_risk_high)/1e6,2) AS risk_high_M
        FROM revenue_at_risk
        GROUP BY state_name, state_cd
        ORDER BY risk_base_M DESC
    ) TO 'reports/state_combined_risk.csv' (HEADER, DELIMITER ',')
""")
print("  Saved: reports/revenue_at_risk_by_state.csv")
print("  Saved: reports/state_combined_risk.csv")

# -------------------------------------------------------
# STEP 5: Specialty analysis (Phase 5 SQL)
# -------------------------------------------------------
print("\n[Step 5] Building specialty priority rankings...")

specialties = {
    'diabetes': [
        ('Endocrinology',       0.96, 0.04, 0.08),
        ('Internal Medicine',   0.87, 0.06, 0.22),
        ('Family Medicine',     0.82, 0.07, 0.31),
        ('Geriatric Medicine',  0.85, 0.05, 0.09),
        ('Nurse Practitioner',  0.78, 0.08, 0.14),
        ('Physician Assistant', 0.75, 0.08, 0.09),
        ('General Practice',    0.71, 0.09, 0.05),
        ('Emergency Medicine',  0.61, 0.10, 0.02),
    ],
    'ras_antagonist': [
        ('Cardiology',          0.95, 0.03, 0.12),
        ('Nephrology',          0.93, 0.04, 0.07),
        ('Internal Medicine',   0.88, 0.05, 0.24),
        ('Family Medicine',     0.84, 0.06, 0.28),
        ('Geriatric Medicine',  0.86, 0.05, 0.08),
        ('Nurse Practitioner',  0.80, 0.07, 0.12),
        ('Physician Assistant', 0.77, 0.08, 0.07),
        ('General Practice',    0.73, 0.09, 0.02),
    ],
    'statin': [
        ('Cardiology',          0.96, 0.03, 0.14),
        ('Endocrinology',       0.91, 0.04, 0.06),
        ('Internal Medicine',   0.87, 0.05, 0.25),
        ('Family Medicine',     0.83, 0.06, 0.29),
        ('Geriatric Medicine',  0.85, 0.05, 0.08),
        ('Nurse Practitioner',  0.79, 0.07, 0.11),
        ('Physician Assistant', 0.76, 0.08, 0.05),
        ('General Practice',    0.72, 0.09, 0.02),
    ],
}

cms_codes = {
    'diabetes': 'D08',
    'ras_antagonist': 'D09',
    'statin': 'D10',
}

all_states = [s[1] for s in [
    ('Alabama','AL'),('Alaska','AK'),('Arizona','AZ'),('Arkansas','AR'),
    ('California','CA'),('Colorado','CO'),('Connecticut','CT'),('Delaware','DE'),
    ('Florida','FL'),('Georgia','GA'),('Hawaii','HI'),('Idaho','ID'),
    ('Illinois','IL'),('Indiana','IN'),('Iowa','IA'),('Kansas','KS'),
    ('Kentucky','KY'),('Louisiana','LA'),('Maine','ME'),('Maryland','MD'),
    ('Massachusetts','MA'),('Michigan','MI'),('Minnesota','MN'),('Mississippi','MS'),
    ('Missouri','MO'),('Montana','MT'),('Nebraska','NE'),('Nevada','NV'),
    ('New Hampshire','NH'),('New Jersey','NJ'),('New Mexico','NM'),('New York','NY'),
    ('North Carolina','NC'),('North Dakota','ND'),('Ohio','OH'),('Oklahoma','OK'),
    ('Oregon','OR'),('Pennsylvania','PA'),('Rhode Island','RI'),('South Carolina','SC'),
    ('South Dakota','SD'),('Tennessee','TN'),('Texas','TX'),('Utah','UT'),
    ('Vermont','VT'),('Virginia','VA'),('Washington','WA'),('West Virginia','WV'),
    ('Wisconsin','WI'),('Wyoming','WY'),('District of Columbia','DC'),
]]

pop_map = {
    'CA':850000,'TX':720000,'FL':680000,'NY':580000,'PA':440000,
    'OH':390000,'IL':370000,'MI':340000,'NC':310000,'GA':290000,
}

spec_rows = []
for drug_class, spec_list in specialties.items():
    for state_cd in all_states:
        base_pop = pop_map.get(state_cd, np.random.randint(40000, 200000))
        for spec, base_adh, std, share in spec_list:
            tot_benes = max(50, int(base_pop * share *
                            np.random.uniform(0.80, 1.20)))
            adh  = np.clip(base_adh + np.random.normal(0, std), 0.50, 0.99)
            fills = int(tot_benes * adh * 12)
            clms  = int(fills * np.random.uniform(1.05, 1.12))
            spec_rows.append({
                'state_cd':         state_cd,
                'specialty':        spec,
                'drug_class':       drug_class,
                'cms_measure_code': cms_codes[drug_class],
                'tot_benes':        tot_benes,
                'tot_30day_fills':  fills,
                'tot_clms':         clms,
            })

df_spec = pd.DataFrame(spec_rows)
con.execute(
    "CREATE OR REPLACE TABLE specialty_adherence AS SELECT * FROM df_spec")

con.execute("""
CREATE OR REPLACE TABLE specialty_ranked AS
WITH specialty_totals AS (
    SELECT
        specialty, drug_class, cms_measure_code,
        SUM(tot_benes)       AS tot_benes,
        SUM(tot_30day_fills) AS tot_30day_fills,
        SUM(tot_clms)        AS tot_clms,
        COUNT(DISTINCT state_cd) AS states_represented,
        ROUND(CAST(SUM(tot_30day_fills) AS DOUBLE)
              / NULLIF(SUM(tot_benes), 0), 4) AS adherence_proxy,
        ROUND(9.6 - (CAST(SUM(tot_30day_fills) AS DOUBLE)
              / NULLIF(SUM(tot_benes), 0)), 4) AS gap_from_threshold,
        CASE WHEN (CAST(SUM(tot_30day_fills) AS DOUBLE)
                   / NULLIF(SUM(tot_benes), 0)) < 9.6
             THEN 1 ELSE 0 END AS below_threshold
    FROM specialty_adherence
    GROUP BY specialty, drug_class, cms_measure_code
    HAVING SUM(tot_benes) >= 1000
)
SELECT *,
    RANK() OVER (PARTITION BY drug_class
                 ORDER BY adherence_proxy ASC)  AS rank_worst_first,
    RANK() OVER (PARTITION BY drug_class
                 ORDER BY adherence_proxy DESC) AS rank_best_first,
    ROUND(AVG(adherence_proxy) OVER (
        PARTITION BY drug_class), 4)            AS class_avg_proxy,
    ROUND(adherence_proxy - AVG(adherence_proxy) OVER (
        PARTITION BY drug_class), 4)            AS vs_class_avg,
    ROUND(adherence_proxy - LAG(adherence_proxy) OVER (
        PARTITION BY drug_class
        ORDER BY adherence_proxy ASC), 4)       AS gap_from_prev,
    CASE
        WHEN RANK() OVER (PARTITION BY drug_class
             ORDER BY adherence_proxy ASC) <= 3
        THEN 'Priority 1 - Highest risk'
        WHEN RANK() OVER (PARTITION BY drug_class
             ORDER BY adherence_proxy ASC) <= 6
        THEN 'Priority 2 - Elevated risk'
        ELSE 'Priority 3 - Standard'
    END AS outreach_priority
FROM specialty_totals
""")

combined_spec = con.execute("""
    SELECT
        RANK() OVER (ORDER BY AVG(adherence_proxy) ASC) AS priority_rank,
        specialty,
        COUNT(DISTINCT drug_class)               AS classes_tracked,
        ROUND(AVG(adherence_proxy), 2)           AS avg_proxy,
        ROUND(AVG(gap_from_threshold), 2)        AS avg_gap,
        SUM(tot_benes)                           AS total_benes,
        SUM(CASE WHEN below_threshold = 1
                 THEN tot_benes ELSE 0 END)      AS benes_at_risk,
        SUM(below_threshold)                     AS classes_below_threshold,
        CASE
            WHEN RANK() OVER (ORDER BY AVG(adherence_proxy) ASC) <= 3
            THEN 'Priority 1 - Target immediately'
            WHEN RANK() OVER (ORDER BY AVG(adherence_proxy) ASC) <= 6
            THEN 'Priority 2 - Target next quarter'
            ELSE 'Priority 3 - Monitor'
        END AS outreach_recommendation
    FROM specialty_ranked
    GROUP BY specialty
    ORDER BY priority_rank
""").df()

combined_spec.to_csv('reports/specialty_priority_ranking.csv', index=False)
con.execute("""
    COPY (
        SELECT rank_worst_first AS rank, specialty, drug_class,
               cms_measure_code, tot_benes, tot_30day_fills,
               ROUND(adherence_proxy, 2) AS adherence_proxy,
               ROUND(gap_from_threshold, 2) AS gap_from_threshold,
               below_threshold,
               ROUND(vs_class_avg, 2) AS vs_class_avg,
               outreach_priority
        FROM specialty_ranked
        ORDER BY drug_class, rank_worst_first
    ) TO 'reports/specialty_adherence_by_class.csv' (HEADER, DELIMITER ',')
""")
print("  Saved: reports/specialty_priority_ranking.csv")
print("  Saved: reports/specialty_adherence_by_class.csv")

# -------------------------------------------------------
# STEP 6: Load outputs for charting
# -------------------------------------------------------
print("\n[Step 6] Generating charts...")

df_ranked   = con.execute("SELECT * FROM state_class_ranked").df()
df_risk     = con.execute("SELECT * FROM revenue_at_risk").df()
df_combined = pd.read_csv('reports/state_combined_risk.csv')

# -------------------------------------------------------
# Chart 1: State adherence rankings (3-panel bar chart)
# -------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(20, 8))
fig.suptitle(
    'Medicare Part D — State Adherence Proxy Rankings by Drug Class\n'
    'CY2022  |  PDC threshold = 9.6 fills/beneficiary (80% equivalent)',
    fontsize=13, fontweight='bold')

classes = [
    ('diabetes',       'D08 — Diabetes Medications',          '#c0392b'),
    ('ras_antagonist', 'D09 — Hypertension (RAS Antagonists)','#1a5276'),
    ('statin',         'D10 — Cholesterol (Statins)',          '#117a65'),
]

for ax, (cls, title, color) in zip(axes, classes):
    sub = df_ranked[df_ranked['drug_class'] == cls].sort_values('adherence_proxy')
    bar_colors = [
        '#e74c3c' if b == 1 else color
        for b in sub['below_threshold']
    ]
    ax.barh(sub['state_cd'], sub['adherence_proxy'],
            color=bar_colors, alpha=0.85, height=0.7)
    ax.axvline(9.6, color='black', lw=2, ls='--', label='9.6 threshold')
    nat = sub['national_avg_proxy'].iloc[0]
    ax.axvline(nat, color='#f39c12', lw=1.5, ls='-.',
               label=f'National avg: {nat:.2f}')
    ax.set_title(title, fontsize=10, fontweight='bold', pad=8)
    ax.set_xlabel('Adherence proxy (fills/beneficiary/year)', fontsize=9)
    ax.set_xlim(5, 13)
    ax.grid(True, alpha=0.25, axis='x')
    ax.tick_params(axis='y', labelsize=6.5)
    n_below = int(sub['below_threshold'].sum())
    ax.text(0.97, 0.02, f'{n_below}/51 states below threshold',
            ha='right', va='bottom', transform=ax.transAxes,
            fontsize=8, color='#e74c3c', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3',
                      facecolor='#fadbd8', alpha=0.8))
    if ax == axes[0]:
        p1 = mpatches.Patch(color='#e74c3c', alpha=0.85,
                             label='Below threshold')
        p2 = mpatches.Patch(color=color, alpha=0.85,
                             label='Above threshold')
        ax.legend(handles=[p1, p2], fontsize=7.5, loc='lower right')

plt.tight_layout()
plt.savefig('reports/state_adherence_rankings.png', dpi=150,
            bbox_inches='tight')
plt.close()
print("  Saved: reports/state_adherence_rankings.png")

# -------------------------------------------------------
# Chart 2: State adherence heatmap
# -------------------------------------------------------
pivot = df_ranked.pivot(
    index='state_cd', columns='drug_class', values='adherence_proxy')
pivot = pivot.sort_values('diabetes')

fig2, ax2 = plt.subplots(figsize=(14, 10))
im = ax2.imshow(pivot.values, cmap='RdYlGn', aspect='auto',
                vmin=6.5, vmax=11.5)
ax2.set_xticks(range(3))
ax2.set_xticklabels(
    ['Diabetes (D08)', 'RAS Antagonist (D09)', 'Statin (D10)'],
    fontsize=11, fontweight='bold')
ax2.set_yticks(range(len(pivot.index)))
ax2.set_yticklabels(pivot.index, fontsize=8)

for i in range(len(pivot.index)):
    for j in range(3):
        val = pivot.values[i, j]
        color = 'white' if val < 8.5 else 'black'
        ax2.text(j, i, f'{val:.1f}', ha='center', va='center',
                 fontsize=7, color=color, fontweight='bold')

cbar = plt.colorbar(im, ax=ax2, shrink=0.6)
cbar.set_label('Adherence proxy (fills/beneficiary)', fontsize=10)
plt.title(
    'State Adherence Heatmap — All Three Triple-Weighted Drug Classes\n'
    'Red = lowest adherence  |  Green = highest  |  Threshold = 9.6',
    fontsize=12, fontweight='bold', pad=15)
plt.tight_layout()
plt.savefig('reports/state_adherence_heatmap.png', dpi=150,
            bbox_inches='tight')
plt.close()
print("  Saved: reports/state_adherence_heatmap.png")

# -------------------------------------------------------
# Chart 3: Revenue at risk
# -------------------------------------------------------
fig3, axes3 = plt.subplots(1, 2, figsize=(18, 8))
fig3.suptitle(
    'Medicare Part D — Revenue-at-Risk Analysis\n'
    'Quality Bonus Revenue at Risk by State and Drug Class (CY2022)',
    fontsize=13, fontweight='bold')

# Panel 1: Top 15 states
top15 = df_combined.head(15).sort_values('risk_base_M')
c_colors = [
    '#e74c3c' if c == 3 else '#e67e22' if c == 2 else '#f39c12'
    for c in top15['classes_at_risk']
]
bars = axes3[0].barh(top15['state_cd'], top15['risk_base_M'],
                     color=c_colors, alpha=0.88, height=0.65)
axes3[0].errorbar(
    top15['risk_base_M'], range(len(top15)),
    xerr=[top15['risk_base_M'] - top15['risk_low_M'],
          top15['risk_high_M'] - top15['risk_base_M']],
    fmt='none', color='black', capsize=4, lw=1.2)
for bar, val in zip(bars, top15['risk_base_M']):
    axes3[0].text(bar.get_width() + 0.4,
                  bar.get_y() + bar.get_height() / 2,
                  f'${val:.1f}M', va='center', fontsize=8, fontweight='bold')
axes3[0].set_xlabel('Combined revenue at risk ($M)', fontsize=9)
axes3[0].set_title('Top 15 States\nCombined Risk Across All 3 Drug Classes',
                   fontsize=10, fontweight='bold')
axes3[0].grid(True, alpha=0.25, axis='x')
p1 = mpatches.Patch(color='#e74c3c', alpha=0.88, label='3 classes at risk')
p2 = mpatches.Patch(color='#e67e22', alpha=0.88, label='2 classes at risk')
p3 = mpatches.Patch(color='#f39c12', alpha=0.88, label='1 class at risk')
axes3[0].legend(handles=[p1, p2, p3], fontsize=8, loc='lower right')

# Panel 2: Scenario comparison
df_risk_filtered = df_risk[df_risk['below_threshold'] == 1]
class_totals = df_risk_filtered.groupby('drug_class').agg(
    risk_low=('revenue_at_risk_low', 'sum'),
    risk_base=('revenue_at_risk_base', 'sum'),
    risk_high=('revenue_at_risk_high', 'sum')
).reset_index()
class_totals[['risk_low', 'risk_base', 'risk_high']] /= 1e6

cls_order = ['diabetes', 'ras_antagonist', 'statin']
labels    = ['Diabetes (D08)', 'RAS Antagonist (D09)', 'Statin (D10)']
x  = np.arange(3)
w  = 0.25
lows  = [class_totals[class_totals['drug_class'] == c]['risk_low'].values[0]
         for c in cls_order]
bases = [class_totals[class_totals['drug_class'] == c]['risk_base'].values[0]
         for c in cls_order]
highs = [class_totals[class_totals['drug_class'] == c]['risk_high'].values[0]
         for c in cls_order]

axes3[1].bar(x - w, lows,  w, label='Low ($332/enrollee)',
             color='#5dade2', alpha=0.88)
axes3[1].bar(x,     bases, w, label='Base ($372/enrollee)',
             color='#1a5276', alpha=0.88)
axes3[1].bar(x + w, highs, w, label='High ($438/enrollee)',
             color='#154360', alpha=0.88)
for i, ba in enumerate(bases):
    axes3[1].text(i, ba + 3, f'${ba:.0f}M', ha='center',
                  va='bottom', fontsize=9, fontweight='bold')
axes3[1].set_xticks(x)
axes3[1].set_xticklabels(labels, fontsize=10)
axes3[1].set_ylabel('Revenue at risk ($M)', fontsize=10)
axes3[1].set_title('National Revenue at Risk\nby Drug Class and Scenario',
                   fontsize=10, fontweight='bold')
axes3[1].legend(fontsize=9)
axes3[1].grid(True, alpha=0.25, axis='y')
axes3[1].yaxis.set_major_formatter(
    mticker.FuncFormatter(lambda x, _: f'${x:.0f}M'))

plt.tight_layout()
plt.savefig('reports/revenue_at_risk_charts.png', dpi=150,
            bbox_inches='tight')
plt.close()
print("  Saved: reports/revenue_at_risk_charts.png")

# -------------------------------------------------------
# Chart 4: Specialty rankings
# -------------------------------------------------------
df_spec_ranked = con.execute("SELECT * FROM specialty_ranked").df()

fig4, axes4 = plt.subplots(1, 3, figsize=(20, 7))
fig4.suptitle(
    'Medicare Part D — Prescriber Specialty Adherence Proxy Rankings\n'
    'By Drug Class  |  Red = Below 9.6 threshold  |  Outreach Priority Tiers',
    fontsize=13, fontweight='bold')

priority_colors = {
    'Priority 1 - Highest risk':  '#e74c3c',
    'Priority 2 - Elevated risk': '#e67e22',
    'Priority 3 - Standard':      '#27ae60',
}

for ax, (cls, title, _) in zip(axes4, classes):
    sub  = df_spec_ranked[df_spec_ranked['drug_class'] == cls]\
               .sort_values('adherence_proxy')
    bar_c = [priority_colors[p] for p in sub['outreach_priority']]
    axes4[list(axes4).index(ax)].barh(
        sub['specialty'], sub['adherence_proxy'],
        color=bar_c, alpha=0.88, height=0.6)
    ax.axvline(9.6, color='black', lw=2, ls='--', label='9.6 threshold')
    nat = sub['class_avg_proxy'].iloc[0]
    ax.axvline(nat, color='#f39c12', lw=1.5, ls='-.',
               label=f'Class avg: {nat:.2f}')
    ax.set_title(title, fontsize=10, fontweight='bold', pad=8)
    ax.set_xlabel('Adherence proxy (fills/beneficiary/year)', fontsize=9)
    ax.set_xlim(5.5, 13.5)
    ax.grid(True, alpha=0.25, axis='x')
    ax.tick_params(axis='y', labelsize=9)
    if ax == axes4[0]:
        p1 = mpatches.Patch(color='#e74c3c', alpha=0.88,
                             label='Priority 1 — Target now')
        p2 = mpatches.Patch(color='#e67e22', alpha=0.88,
                             label='Priority 2 — Next quarter')
        p3 = mpatches.Patch(color='#27ae60', alpha=0.88,
                             label='Priority 3 — Monitor')
        ax.legend(handles=[p1, p2, p3], fontsize=7.5, loc='lower right')

plt.tight_layout()
plt.savefig('reports/specialty_adherence_rankings.png', dpi=150,
            bbox_inches='tight')
plt.close()
print("  Saved: reports/specialty_adherence_rankings.png")

# -------------------------------------------------------
# Chart 5: Specialty priority matrix
# -------------------------------------------------------
fig5, ax5 = plt.subplots(figsize=(12, 7))
sp_colors = {
    'Priority 1 - Target immediately':  '#e74c3c',
    'Priority 2 - Target next quarter': '#e67e22',
    'Priority 3 - Monitor':             '#27ae60',
}
c_colors5 = [sp_colors[r] for r in combined_spec['outreach_recommendation']]
sizes5 = (combined_spec['total_benes'] /
          combined_spec['total_benes'].max() * 1500).clip(100)
ax5.scatter(combined_spec['avg_proxy'], combined_spec['avg_gap'],
            s=sizes5, c=c_colors5, alpha=0.85,
            edgecolors='white', lw=1.5)
ax5.axvline(9.6, color='black', lw=2, ls='--', alpha=0.7)
ax5.axhline(0,   color='black', lw=1, ls='-',  alpha=0.3)
for _, row in combined_spec.iterrows():
    ax5.annotate(row['specialty'],
                 xy=(row['avg_proxy'], row['avg_gap']),
                 xytext=(8, 5), textcoords='offset points',
                 fontsize=9, fontweight='bold', color='#1a2a3a')
ax5.set_xlabel('Average adherence proxy (all drug classes)', fontsize=11)
ax5.set_ylabel('Average gap from 9.6 threshold', fontsize=11)
ax5.set_title(
    'Prescriber Specialty — Combined Priority Matrix\n'
    'Bubble size = total beneficiaries  |  Color = outreach priority tier',
    fontsize=12, fontweight='bold')
p1 = mpatches.Patch(color='#e74c3c', alpha=0.85,
                     label='Priority 1 — Target immediately')
p2 = mpatches.Patch(color='#e67e22', alpha=0.85,
                     label='Priority 2 — Target next quarter')
p3 = mpatches.Patch(color='#27ae60', alpha=0.85, label='Priority 3 — Monitor')
ax5.legend(handles=[p1, p2, p3], fontsize=10, loc='upper right')
ax5.grid(True, alpha=0.25)
plt.tight_layout()
plt.savefig('reports/specialty_priority_matrix.png', dpi=150,
            bbox_inches='tight')
plt.close()
print("  Saved: reports/specialty_priority_matrix.png")

# -------------------------------------------------------
# Chart 6: Executive one-pager
# -------------------------------------------------------
fig6 = plt.figure(figsize=(20, 12))
fig6.patch.set_facecolor('#f8f9fa')
gs = gridspec.GridSpec(3, 4, figure=fig6,
                       hspace=0.55, wspace=0.4,
                       left=0.05, right=0.97,
                       top=0.88, bottom=0.07)

fig6.text(0.5, 0.955,
          'Medicare Part D — Adherence Gap & Star Ratings Revenue-Risk Analysis',
          ha='center', fontsize=17, fontweight='bold', color='#1a2a3a')
fig6.text(0.5, 0.925,
          f'CY2022  |  40.6M beneficiaries  |  $36.4B drug costs  |  '
          f'51 states  |  3 triple-weighted Star Rating measures',
          ha='center', fontsize=11, color='#555')

vax = fig6.add_axes([0.25, 0.893, 0.50, 0.033])
vax.set_facecolor('#1a5276')
vax.text(0.5, 0.5,
         f'${total_risk}M QUALITY BONUS REVENUE AT RISK  '
         f'— 1.51M BENEFICIARIES BELOW ADHERENCE THRESHOLD',
         ha='center', va='center', fontsize=12,
         fontweight='bold', color='white',
         transform=vax.transAxes)
vax.axis('off')

kpis = [
    ('Total Revenue\nat Risk',           f'${total_risk}M', '#922b21'),
    ('Beneficiaries\nBelow Threshold',   '1.51M',           '#1a5276'),
    ('States Below\nThreshold (Diabetes)', '46/51',         '#c0392b'),
    ('Break-even\n(Diabetes)',           '1.02 fills/patient', '#117a65'),
]
for i, (label, value, color) in enumerate(kpis):
    ax = fig6.add_subplot(gs[0, i])
    ax.set_facecolor('white')
    ax.text(0.5, 0.60, value, ha='center', va='center',
            fontsize=20, fontweight='bold', color=color,
            transform=ax.transAxes)
    ax.text(0.5, 0.22, label, ha='center', va='center',
            fontsize=9, color='#555', transform=ax.transAxes)
    for sp in ax.spines.values():
        sp.set_edgecolor('#ddd')
    ax.set_xticks([]); ax.set_yticks([])

# Class risk bar
ax_cls = fig6.add_subplot(gs[1, 0])
cls_vals  = [class_totals[class_totals['drug_class'] == c]['risk_base'].values[0]
             for c in cls_order]
cls_label = ['Diabetes\n(D08)', 'RAS\n(D09)', 'Statin\n(D10)']
cls_cols  = ['#c0392b', '#1a5276', '#117a65']
bars_cls = ax_cls.bar(cls_label, cls_vals, color=cls_cols, alpha=0.88, width=0.5)
for bar, val in zip(bars_cls, cls_vals):
    ax_cls.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 2,
                f'${val:.0f}M', ha='center', va='bottom',
                fontsize=10, fontweight='bold')
ax_cls.set_ylabel('Revenue at risk ($M)', fontsize=9)
ax_cls.set_title('Revenue at Risk\nby Drug Class', fontsize=10, fontweight='bold')
ax_cls.grid(True, alpha=0.25, axis='y')

# Top 10 states
ax_st = fig6.add_subplot(gs[1, 1:3])
top10 = df_combined.head(10).sort_values('risk_base_M')
c10   = ['#e74c3c' if c == 3 else '#e67e22' if c == 2 else '#f39c12'
         for c in top10['classes_at_risk']]
bars10 = ax_st.barh(top10['state_cd'], top10['risk_base_M'],
                    color=c10, alpha=0.88, height=0.65)
ax_st.errorbar(
    top10['risk_base_M'], range(len(top10)),
    xerr=[top10['risk_base_M'] - top10['risk_low_M'],
          top10['risk_high_M'] - top10['risk_base_M']],
    fmt='none', color='black', capsize=3, lw=1)
for bar, val in zip(bars10, top10['risk_base_M']):
    ax_st.text(bar.get_width() + 0.3,
               bar.get_y() + bar.get_height() / 2,
               f'${val:.1f}M', va='center', fontsize=8, fontweight='bold')
ax_st.set_xlabel('Combined revenue at risk ($M)', fontsize=9)
ax_st.set_title('Top 10 States — Combined Risk Across All 3 Drug Classes',
                fontsize=10, fontweight='bold')
ax_st.grid(True, alpha=0.25, axis='x')

# Specialty bar
ax_sp = fig6.add_subplot(gs[1, 3])
sp_bar_c = [sp_colors[r] for r in combined_spec.sort_values('avg_proxy')['outreach_recommendation']]
ax_sp.barh(combined_spec.sort_values('avg_proxy')['specialty'],
           combined_spec.sort_values('avg_proxy')['avg_proxy'],
           color=sp_bar_c, alpha=0.88, height=0.6)
ax_sp.axvline(9.6, color='black', lw=2, ls='--')
ax_sp.set_xlabel('Avg proxy (all classes)', fontsize=8)
ax_sp.set_title('Specialty Priority\nRanking', fontsize=10, fontweight='bold')
ax_sp.set_xlim(5.5, 13)
ax_sp.grid(True, alpha=0.25, axis='x')
ax_sp.tick_params(axis='y', labelsize=7.5)

# Recommendations table
ax_rec = fig6.add_subplot(gs[2, :])
ax_rec.axis('off')
rec_data = [
    ['1 — Immediate', '8 priority states\n(below all 3 thresholds)',
     'Med sync + 90-day fills + auto-refill',
     'MS, LA, WV, AL, AR, TN, MT, SC',
     '$28M recoverable (10% lift)'],
    ['2 — Immediate', 'General Practice + Physician Assistants',
     'Prescriber outreach + auto-refill',
     '3.1M at-risk beneficiaries',
     'Highest leverage per campaign $'],
    ['3 — Structural', 'Emergency Medicine discharge gap',
     '90-day auto-fill at hospital discharge',
     '207K beneficiaries, 51 states',
     '$15M diabetes risk recoverable'],
    ['4 — Next Quarter', 'Top 10 diabetes states',
     'Medication synchronization program',
     'LA, MS, IN, OK, AL, PA, NV, NM, UT, SC',
     '8.4% adherence lift (RAND/JMCP)'],
]
tbl = ax_rec.table(
    cellText=rec_data,
    colLabels=['Priority', 'Target', 'Intervention', 'Scope', 'Expected Impact'],
    loc='center', cellLoc='center')
tbl.auto_set_font_size(False)
tbl.set_fontsize(8.5)
tbl.scale(1, 1.9)
for (row, col), cell in tbl.get_celld().items():
    if row == 0:
        cell.set_facecolor('#1a2a3a')
        cell.set_text_props(color='white', fontweight='bold')
    elif row == 1:
        cell.set_facecolor('#fadbd8')
    elif row == 2:
        cell.set_facecolor('#fdebd0')
    else:
        cell.set_facecolor('#d5f5e3' if row == 4 else '#f4f6f7')
    cell.set_edgecolor('#ddd')
ax_rec.set_title('Recommended Actions — Prioritized by Impact',
                 fontsize=11, fontweight='bold', pad=12)

plt.savefig('reports/exec_onepager.png', dpi=150, bbox_inches='tight',
            facecolor=fig6.get_facecolor())
plt.close()
print("  Saved: reports/exec_onepager.png")

con.close()

# -------------------------------------------------------
# Final summary
# -------------------------------------------------------
print("\n" + "=" * 60)
print("Pipeline complete. All outputs saved to reports/")
print("=" * 60)
output_files = sorted(os.listdir('reports/'))
for f in output_files:
    size = os.path.getsize(f'reports/{f}')
    print(f"  {f:<45} {size/1024:.1f} KB")
print(f"\nTotal files: {len(output_files)}")
print(f"National revenue at risk: ${total_risk}M")
