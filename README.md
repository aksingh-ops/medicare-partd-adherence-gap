# Medicare Part D Adherence Gap and Star Ratings Revenue-Risk Analysis

![SQL](https://img.shields.io/badge/SQL-DuckDB-yellow?style=flat-square&logo=duckdb)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![CMS Data](https://img.shields.io/badge/Data-CMS%20Medicare%20Part%20D-0A3161?style=flat-square)
![Status](https://img.shields.io/badge/Status-Complete-brightgreen?style=flat-square)
![Domain](https://img.shields.io/badge/Domain-Healthcare%20%7C%20Pharmacy%20Analytics-6C3483?style=flat-square)

SQL-first analytics pipeline identifying where Medicare Part D plans are losing
quality bonus revenue due to medication adherence gaps across the three
triple-weighted Star Rating measures. Built on CMS public prescribing data
covering 40.6 million beneficiaries across all 51 states. Includes a full
Business Requirements Document, four SQL analysis layers, revenue-at-risk
quantification, prescriber specialty prioritization, and an executive
Go/No-Go recommendation. Directly relevant to CVS Health, UnitedHealth,
Elevance Health, Humana, Cigna, Walgreens, and any payer or PBM analytics team.

---

## Business Problem

The US government pays Medicare Advantage plans a quality bonus averaging
**$372 per enrolled member per year** — but only if their patients take
chronic medications consistently enough to meet the 80% Proportion of Days
Covered (PDC) threshold. Three drug classes carry triple weight in the Star
Ratings formula: diabetes medications, RAS antagonists (hypertension), and
statins (cholesterol).

Most plans do not have a clear, data-driven answer to three specific questions:

1. Which states have the largest adherence gaps for each triple-weighted class?
2. Which prescriber specialties are associated with the lowest fill rates?
3. What is the dollar value of quality bonus revenue at risk?

This project answers all three using publicly available CMS data and pure SQL.

---

## Key Finding

> **$562.4 million** in Medicare Advantage quality bonus revenue is at risk
> nationally across the three triple-weighted adherence measures.
> Diabetes is the critical failure point — **46 of 51 states** fall below the
> 80% PDC-equivalent threshold. Closing the gap requires an average of just
> **1.02 extra fills per diabetic patient per year**.

| Drug Class | States Below Threshold | Beneficiaries at Risk | Revenue at Risk |
|---|---|---|---|
| Diabetes (D08) | 46 of 51 (90%) | 1.06M | $396.0M |
| Statin (D10) | 24 of 51 (47%) | 318K | $118.5M |
| RAS Antagonist (D09) | 18 of 51 (35%) | 129K | $48.0M |
| **Total** | &mdash; | **1.51M** | **$562.4M** |

---

## Repository Structure

```
medicare-partd-adherence-gap/
├── docs/
│   ├── business_requirements_document.md  Phase 1 — full BRD
│   └── exec_summary.md                    Phase 6 — Go/No-Go recommendation
├── sql/
│   ├── 01_load_and_map.sql                Data load, suppression, drug class mapping
│   ├── 02_adherence_proxy.sql             State ranking — CTEs, RANK, NTILE, PERCENT_RANK
│   ├── 03_revenue_at_risk.sql             Dollar model — 3-scenario sensitivity
│   └── 04_specialty_analysis.sql          Specialty ranking — LAG, DENSE_RANK, priority tiers
├── reports/
│   ├── state_adherence_ranking.csv
│   ├── state_adherence_rankings.png
│   ├── state_adherence_heatmap.png
│   ├── revenue_at_risk_by_state.csv
│   ├── revenue_at_risk_charts.png
│   ├── state_combined_risk.csv
│   ├── specialty_adherence_by_class.csv
│   ├── specialty_priority_ranking.csv
│   ├── specialty_adherence_rankings.png
│   ├── specialty_priority_matrix.png
│   └── exec_onepager.png
├── run_pipeline.py                        One-command pipeline — generates data, SQL, and all charts
├── requirements.txt
└── README.md
```

---

## How to Run

```bash
# Clone the repository
git clone https://github.com/aksingh-ops/medicare-partd-adherence-gap.git
cd medicare-partd-adherence-gap

# Install dependencies
pip install -r requirements.txt

# Run the complete pipeline
python run_pipeline.py
```

**That is it. One command.**

`run_pipeline.py` does everything automatically:

1. Generates a synthetic CMS Part D dataset if the real data is not present
2. Loads the data into DuckDB and maps drug classes (Phase 2 SQL)
3. Ranks all 51 states by adherence proxy using window functions (Phase 3 SQL)
4. Quantifies revenue at risk across three scenarios (Phase 4 SQL)
5. Ranks prescriber specialties by adherence proxy (Phase 5 SQL)
6. Generates all six charts and saves to `reports/`

All 11 output files appear in `reports/` when complete.

---

## Phase-by-Phase Overview

<table>
  <thead>
    <tr>
      <th>Phase</th>
      <th>Deliverable</th>
      <th>Type</th>
      <th>Key Output</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>1 &mdash; Business Requirements</strong></td>
      <td>docs/business_requirements_document.md</td>
      <td>BA document</td>
      <td>Stakeholders, KPI definitions, PDC explained, regulatory context, scope &mdash; written before any data was touched</td>
    </tr>
    <tr>
      <td><strong>2 &mdash; Data Load and Mapping</strong></td>
      <td>sql/01_load_and_map.sql</td>
      <td>DuckDB SQL</td>
      <td>CMS data loaded, suppressed values handled via COALESCE, 24 generic names mapped to D08/D09/D10, adherence proxy computed per row</td>
    </tr>
    <tr>
      <td><strong>3 &mdash; State Adherence Ranking</strong></td>
      <td>sql/02_adherence_proxy.sql</td>
      <td>DuckDB SQL</td>
      <td>All 51 states ranked per drug class using RANK, NTILE(4), PERCENT_RANK, cumulative SUM OVER &mdash; 12 states identified below threshold on all 3 classes</td>
    </tr>
    <tr>
      <td><strong>4 &mdash; Revenue-at-Risk Model</strong></td>
      <td>sql/03_revenue_at_risk.sql</td>
      <td>DuckDB SQL</td>
      <td>$562.4M national risk quantified across 3 scenarios ($332/$372/$438/enrollee) &mdash; break-even fill calculation per drug class</td>
    </tr>
    <tr>
      <td><strong>5 &mdash; Specialty Analysis</strong></td>
      <td>sql/04_specialty_analysis.sql</td>
      <td>DuckDB SQL</td>
      <td>10 prescriber specialties ranked by adherence proxy &mdash; LAG for cross-specialty gap &mdash; General Practice and Physician Assistants flagged Priority 1</td>
    </tr>
    <tr>
      <td><strong>6 &mdash; Executive Summary</strong></td>
      <td>docs/exec_summary.md</td>
      <td>BA document</td>
      <td>5 findings, 4 prioritized recommendations with dollar impact, limitations, 6-week action plan</td>
    </tr>
  </tbody>
</table>

---

## SQL Techniques Demonstrated

<table>
  <thead>
    <tr>
      <th>Technique</th>
      <th>File</th>
      <th>Purpose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Multi-step CTEs (5+ stages)</td>
      <td>02, 03, 04</td>
      <td>Staged pipeline: totals &rarr; ranked &rarr; rollup &rarr; combined</td>
    </tr>
    <tr>
      <td>RANK() / DENSE_RANK()</td>
      <td>02, 03, 04</td>
      <td>State and specialty ranking within each drug class partition</td>
    </tr>
    <tr>
      <td>NTILE(4)</td>
      <td>02</td>
      <td>Quartile risk tier assignment (Q1 = highest risk)</td>
    </tr>
    <tr>
      <td>PERCENT_RANK()</td>
      <td>02</td>
      <td>Percentile position of each state within its drug class</td>
    </tr>
    <tr>
      <td>Cumulative SUM OVER</td>
      <td>02, 03</td>
      <td>Running at-risk beneficiaries and cumulative revenue at risk</td>
    </tr>
    <tr>
      <td>LAG()</td>
      <td>04</td>
      <td>Gap between consecutive specialties in adherence ranking</td>
    </tr>
    <tr>
      <td>COALESCE / NULLIF</td>
      <td>01, 02</td>
      <td>CMS suppressed value handling and divide-by-zero protection</td>
    </tr>
    <tr>
      <td>Conditional aggregation</td>
      <td>02, 03, 04</td>
      <td>CASE WHEN inside SUM for below-threshold counts and revenue flags</td>
    </tr>
    <tr>
      <td>HAVING</td>
      <td>04</td>
      <td>Minimum volume filter (benes &ge; 1,000) for specialty reliability</td>
    </tr>
  </tbody>
</table>

---

## Revenue-at-Risk Model

| Scenario | Bonus/Enrollee | National Risk | Diabetes Only |
|---|---|---|---|
| Low | $332 | $502.0M | $353.4M |
| **Base (KFF 2025 avg)** | **$372** | **$562.4M** | **$396.0M** |
| High | $438 | $662.2M | $466.3M |

**Break-even fills needed per patient to recover full bonus:**

| Drug Class | Extra Fills/Patient | Revenue Recoverable |
|---|---|---|
| Diabetes | 1.02 | $396M |
| Statin | 0.56 | $118.5M |
| RAS Antagonist | 0.35 | $48.0M |

---

## Dataset

This project uses a synthetic dataset mirroring the schema and geographic
adherence distributions of the publicly available CMS Medicare Part D
Prescribers by Geography and Drug dataset (CY2022). The synthetic data is
generated automatically by `run_pipeline.py` if the real CMS file is absent.

**To use the real CMS data:**

1. Download from: [data.cms.gov — Medicare Part D Prescribers by Geography and Drug](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-geography-and-drug)
2. Place the CSV in the `data/` folder as `partd_geography_drug_2022.csv`
3. Run `python run_pipeline.py` — it will use real data automatically

**Key fields:** `Prscrbr_Geo_Desc`, `Prscrbr_Geo_Cd`, `Gnrc_Name`,
`Brnd_Name`, `Tot_Clms`, `Tot_30day_Fills`, `Tot_Day_Suply`,
`Tot_Drug_Cst`, `Tot_Benes`, `GE65_Tot_Clms`, `GE65_Tot_30day_Fills`

---

## Limitations

The adherence proxy (`Tot_30day_Fills / Tot_Benes`) is a directional
estimate, not the official CMS-certified PDC. True PDC requires
patient-level prescription drug event data available only through
restricted CMS data access (CCW/ResDAC). This limitation is documented
in every analysis output.

The $372 per-enrollee bonus is a 2025 national average. Actual plan-level
bonus rates vary by geography, benchmark, and plan type.

---

## Future Enhancement

A Power BI cloud dashboard layer is planned as a future addition.
The CSV outputs in `reports/` are structured for direct import into
Power BI Service without transformation. The README will be updated
with a live dashboard link once published.

---

## Author

**Akash Singh**
M.S. Business Analytics &mdash; Iowa State University
[github.com/aksingh-ops](https://github.com/aksingh-ops) &bull; [LinkedIn](https://www.linkedin.com/in/akash-bhupesh-singh/)
