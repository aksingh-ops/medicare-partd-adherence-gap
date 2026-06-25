# Business Requirements Document
## Medicare Part D Adherence Gap and Star Ratings Revenue-Risk Analysis

**Document version:** 1.0  
**Author:** Akash Singh, Data Analyst  
**Date:** June 2026  
**Status:** Approved for analysis  

---

## 1. Executive Context

Medicare Part D is the US federal prescription drug benefit program covering
approximately 50 million Americans. Under the Medicare Advantage program, CMS
assigns each health plan a Star Rating from 1 to 5 based on quality measures
including medication adherence. Plans that achieve 4 or more stars receive a
quality bonus payment — worth an average of $372 per enrolled member per year
in 2025 (KFF, June 2025). Total quality bonus payments across all Medicare
Advantage plans reached $12.7 billion in 2025.

Three medication adherence measures carry triple weight in the Star Ratings
formula — meaning they each count three times more than standard measures
toward the plan's overall score:

- Medication Adherence for Diabetes Medications (non-insulin)
- Medication Adherence for Hypertension (RAS antagonists)
- Medication Adherence for Cholesterol (statins)

Together these three triple-weighted measures represent roughly one-third of a
plan's total Star Rating score. A plan that consistently underperforms on these
three measures cannot achieve 4 stars regardless of performance elsewhere.

CMS defines adherence using Proportion of Days Covered (PDC): a patient is
considered adherent if their prescription supply covers at least 80% of days
in the measurement year. Plans are scored on the percentage of their enrolled
population meeting this 80% PDC threshold.

---

## 2. Business Problem

Despite the financial stakes, the average Star Rating for each of the three
triple-weighted adherence measures hovered just above 3.0 in 2024-2025, with
two of the three measures declining year-over-year (AnewHealth, 2025). This
means the majority of plans are performing at a level that does not qualify
for the full quality bonus.

The problem is not that plans do not care. The problem is that most plans do
not have a clear, data-driven answer to three specific questions:

1. Which geographies (states) have the largest adherence gaps for each of the
   three triple-weighted drug classes?
2. Which prescriber specialties are associated with the lowest fill rates —
   and therefore represent the highest-priority outreach targets?
3. What is the dollar value of the quality bonus revenue at risk if these gaps
   are not closed?

Without answers to these three questions, improvement efforts are unfocused
and resources are wasted on low-impact interventions.

---

## 3. Project Objective

Build a SQL-based analytics pipeline using publicly available CMS Medicare
Part D data to:

- Compute a state-level adherence proxy for each of the three triple-weighted
  drug classes using standardized 30-day fills per beneficiary
- Identify the 10 highest-risk states by adherence gap and revenue at risk
- Rank prescriber specialties by adherence proxy score to surface outreach
  priorities
- Quantify estimated quality bonus revenue at risk nationally and by state
- Deliver a plain-English executive summary and prioritized action plan

---

## 4. Stakeholders

| Role | Organization | Interest |
|---|---|---|
| VP of Pharmacy Analytics | Health plan / PBM | Adherence gap by geography and specialty |
| Medicare Stars Program Manager | Health plan | Which measures to prioritize for improvement |
| Director of Pharmacy Operations | Walgreens / CVS / Retail pharmacy | Which prescriber cohorts to target for outreach |
| CFO / Finance | Health plan | Dollar value of bonus revenue at risk |
| Data Analyst (author) | Analytics team | SQL pipeline, methodology, reporting |

---

## 5. Key Definitions

### Proportion of Days Covered (PDC)
The official CMS/PQA adherence metric. Measures the fraction of days in a
measurement year during which a patient has prescription supply on hand.
A PDC of 0.80 or higher is the adherence threshold.

**Formula (patient level):**
```
PDC = Days with drug supply on hand / Total days in measurement period
```

A patient filling a 30-day supply 12 times per year has continuous coverage
(PDC = 1.0). A patient filling it 9 times has 270 days covered out of 365
(PDC = 0.74 — below threshold).

### Adherence Proxy (this project)
Because the CMS public dataset is aggregated at the state-drug level (not
patient level), true PDC cannot be computed. Instead we use:

```
Adherence Proxy = Tot_30day_Fills / Tot_Benes
```

This gives average standardized 30-day fills per beneficiary per year for a
drug class in a state. The implied PDC-equivalent benchmarks are:

| Fills per beneficiary | Implied coverage | PDC equivalent |
|---|---|---|
| 12.0 | 365 days | ~1.00 (full year) |
| 9.6 | 292 days | ~0.80 (threshold) |
| Below 9.6 | Below threshold | Below 0.80 |

This proxy is a directional estimate, not the official CMS-spec PDC. This
limitation is documented in every output from this project.

### Triple-Weighted Adherence Drug Classes
Three drug classes as defined by CMS/PQA for Star Ratings measures:

| Star Rating Measure | Drug Class | Examples |
|---|---|---|
| D08 — Diabetes Medications | Non-insulin antidiabetics | Metformin, GLP-1 agonists, SGLT2 inhibitors |
| D09 — Hypertension (RAS antagonists) | ACE inhibitors + ARBs | Lisinopril, losartan, ramipril |
| D10 — Cholesterol (Statins) | HMG-CoA reductase inhibitors | Atorvastatin, rosuvastatin, simvastatin |

### Revenue at Risk
Estimated quality bonus revenue a plan loses by falling short of 4-star
performance on adherence measures. Calculated as:

```
Revenue at Risk = Beneficiaries below threshold x $372 (avg bonus/enrollee)
```

$372 is the 2025 average Medicare Advantage quality bonus per enrollee
(KFF Medicare Advantage 2025 Spotlight, June 2025). Used as the base case.
Sensitivity analysis uses $332 (lower bound) and $438 (upper bound) from
the same source.

---

## 6. Data Source

**Dataset:** CMS Medicare Part D Prescribers — by Geography and Drug  
**Publisher:** Centers for Medicare and Medicaid Services (CMS)  
**URL:** https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-geography-and-drug  
**License:** Public domain — free to use, no authentication required  
**Coverage:** Calendar year 2022 (most recent complete year available)  
**Granularity:** State + drug generic name level aggregations  

**Key fields used:**

| Field | Description |
|---|---|
| Prscrbr_Geo_Desc | State name |
| Prscrbr_Geo_Cd | State FIPS code |
| Gnrc_Name | Generic drug name |
| Brnd_Name | Brand drug name |
| Tot_Clms | Total Part D claims |
| Tot_30day_Fills | Standardized 30-day fills |
| Tot_Day_Suply | Total days of drug supply |
| Tot_Drug_Cst | Total drug cost |
| Tot_Benes | Total unique beneficiaries |
| GE65_Tot_Clms | Claims for beneficiaries 65+ |
| GE65_Tot_30day_Fills | 30-day fills for 65+ |

**Data limitation:** Records with fewer than 11 claims are suppressed by CMS
to protect beneficiary privacy. Suppressed values appear as blanks and are
excluded from aggregations.

---

## 7. Analytical Scope

### In scope
- 50 US states plus DC
- Three triple-weighted drug classes only (diabetes, RAS antagonists, statins)
- CY2022 data (most recent complete year)
- State-level and drug class-level analysis
- Prescriber specialty analysis (from by-Provider dataset)
- Revenue-at-risk quantification using $372 base case

### Out of scope
- True patient-level PDC calculation (requires restricted CMS claims data)
- Medicare Part B drugs (administered in clinical settings)
- Opioids, antibiotics, antipsychotics (separate CMS programs)
- Individual plan-level analysis (requires plan enrollment data)
- Projections beyond CY2022 data

---

## 8. Success Metrics

The project is complete and successful when it delivers:

| Deliverable | Description |
|---|---|
| Drug class mapping table | All relevant generic names tagged to diabetes / RAS / statin class |
| State adherence proxy table | Fills-per-beneficiary by state and drug class, ranked |
| Gap flagging | States below 9.6 fills/beneficiary (sub-80% PDC equivalent) flagged |
| Revenue-at-risk table | Dollar estimate by state, drug class, and nationally |
| Specialty ranking | Prescriber specialties ranked by adherence proxy score |
| Executive summary | Plain-English findings with top 10 risk states and 3 recommendations |

---

## 9. KPI Definitions

| KPI | Definition | Target |
|---|---|---|
| Adherence proxy score | Tot_30day_Fills / Tot_Benes for a drug class in a state | >= 9.6 (80% PDC equivalent) |
| Gap size (pp) | 9.6 minus actual proxy score, where proxy < 9.6 | Minimize |
| Beneficiaries at risk | Tot_Benes where proxy < 9.6 | Minimize |
| Revenue at risk ($) | Beneficiaries at risk x $372 | Minimize |
| National gap coverage | % of states meeting 9.6 threshold per drug class | Maximize |

---

## 10. Regulatory and Industry Context

**CMS Star Ratings methodology** (2026 measures, CMS.gov):
- D08: Medication Adherence for Diabetes Medications — weight 3
- D09: Medication Adherence for Hypertension (RAS antagonists) — weight 3
- D10: Medication Adherence for Cholesterol (Statins) — weight 3

**2026 methodology change to note:** For measurement year 2026 only, CMS
temporarily reduced these three measures from triple-weight to single-weight.
They are expected to return to triple-weight in 2027. This project analyzes
2022 data under the triple-weight framework that has been in place since 2012
and is returning in 2027.

**Financial context:**
- $12.7 billion total quality bonus payments in 2025 (KFF)
- $372 average bonus per enrollee (KFF 2025)
- 9.5 percentage point increase in plan enrollment per 1-star rating improvement
  (peer-reviewed, PMC10391096)
- $6.3 billion in quality bonus payments in 2018 alone (PMC10391096)

---

## 11. Assumptions and Constraints

- The $372 per-enrollee bonus figure is used as a proxy for revenue at risk.
  In practice, the bonus calculation involves benchmark rates, rebates, and
  plan-specific enrollment — the $372 is an average across all plan types.
- The adherence proxy (fills per beneficiary) is a directional estimate, not
  a certified PDC computation. Results should be treated as risk indicators,
  not definitive compliance scores.
- CMS data suppression means some state-drug combinations with low volume
  are excluded. This slightly understates gaps in low-population states.
- Analysis uses 2022 data. Adherence patterns may have shifted with the
  widespread adoption of GLP-1 medications post-2022.

---

## 12. Linked Deliverables

| Phase | File | Description |
|---|---|---|
| 2 | sql/01_load_and_map.sql | Data load and drug class mapping |
| 3 | sql/02_adherence_proxy.sql | State-level adherence proxy and gap calculation |
| 4 | sql/03_revenue_at_risk.sql | Dollar quantification by state and drug class |
| 5 | sql/04_specialty_analysis.sql | Prescriber specialty ranking |
| 6 | docs/exec_summary.md | Executive summary and recommendations |
| — | reports/ | All output CSVs and chart exports |

---

## 13. Sign-Off

| Role | Name | Status |
|---|---|---|
| Analytics lead | Akash Singh | Approved |
| Pharmacy analytics stakeholder | [Reviewer] | Pending |
| Finance stakeholder | [Reviewer] | Pending |
