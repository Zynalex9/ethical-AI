# Gap Analysis — Research vs. Product (EthicScan AI Validator)

> **How to read this:** The left column is what the research document promises or implies. The right column is what the codebase actually does. Missing items are organised into implementation phases below.

---

## ✅ What Is Already Built (Strong Coverage)

| Research Goal | Status |
|---|---|
| Fairness: Demographic Parity Ratio, Equalized Odds, Equal Opportunity, Disparate Impact | ✅ Fully implemented via Fairlearn |
| Privacy: PII detection, k-Anonymity, l-Diversity | ✅ Fully implemented |
| Transparency: SHAP global + local, Model Card, accuracy/precision/recall/F1 | ✅ Fully implemented |
| Accountability: MLflow experiment tracking, immutable audit log | ✅ Fully implemented |
| Requirement Elicitation (cognitive RE) from dataset + model | ✅ Fully implemented |
| Template-driven project bootstrap (ETH1–ETH6 domain presets) | ✅ Fully implemented |
| Traceability matrix (requirements → model → dataset → validation) | ✅ Fully implemented |
| Async validation suite with Celery + progress polling | ✅ Fully implemented |
| PDF report download | ✅ Implemented (minimal renderer) |
| Compliance report endpoint | ✅ Implemented |
| Benchmark datasets (Adult Income, COMPAS, German Credit) | ✅ Loaders present |
| Role-based auth (user / admin / auditor) | ✅ Implemented |
| Root-cause analysis page | ✅ Implemented |
| Dataset predictions mode (fairness without a model file) | ✅ Just added |

---

## ❌ Gaps vs. Research Document

### Data & Model Input Gaps

| Research Claims | Reality | Gap |
|---|---|---|
| Dataset formats: CSV, **Excel, Parquet, JSON** | CSV only | Excel/Parquet/JSON not accepted |
| Dataset size up to **2 GB** | Hard-coded **100 MB** limit | 20× smaller than stated |
| Model size up to 100 MB | 100 MB — matches | ✅ |

---

### Metric / Validation Gaps

| Research Claims | Reality | Gap |
|---|---|---|
| **Explanation Fidelity**: `1 − avg(|f(x)−g(x)|)` | Not computed anywhere | Formula defined in research table but never implemented |
| **LIME explanations** | Engine file imports LIME but the transparency validator route does not actually invoke `explain_local_lime()` — results only carry SHAP | LIME outputs never reach the frontend |
| **Differential Privacy** | Mentioned in `suggest_generalization()` as a text recommendation only | No ε-measurement, no Laplace/Gaussian noise application, no actual DP metric |
| Fairness threshold for **Equal Opportunity Difference ≤ 0.05** (research table) | Default threshold is 0.10 | Default differs from the research-defined threshold |

---

### Reporting Gaps

| Research Claims | Reality | Gap |
|---|---|---|
| **HTML report** export | Not present (PDF only) | No HTML rendering endpoint or download |
| **JSON export** download button | API returns JSON but there is no download button in the UI | Frontend has no "Export JSON" action |
| **Compliance certificate** (visually distinct, printable) | Compliance report is a plain JSON object | No certificate-style document / styled PDF |

---

### Monitoring & Lifecycle Gaps

| Research Claims | Reality | Gap |
|---|---|---|
| **Continuous / periodic monitoring** after deployment | Completely absent | No scheduler, no cron, no re-run triggers |
| **Time-series charts** on dashboard (fairness scores over time) | Dashboard has stat cards + trend text only | No line/area charts tracking metric evolution across runs |
| **Alerts / notifications** when a metric drops below threshold | Not present | No email, webhook, or in-app alert system |
| **"Apply Fixes → Retest" workflow** (Section 6.3 Step 7) | User must manually create a new validation from scratch | No "re-run same config" button, no guided fix checklist |

---

### Regulatory / Compliance Scoring Gaps

| Research Claims | Reality | Gap |
|---|---|---|
| **EU AI Act** compliance scoring | Templates reference it in names only | No structured risk-level classification or Article mapping |
| **ECOA 80% Rule** automated check | ETH1 template sets threshold to 0.80 but there is no explicit "ECOA compliant: yes/no" output | Threshold present; compliance label absent |
| **EEOC Four-Fifths Rule** automated check | Same as above for ETH4 | Same gap |
| **GDPR Article 22** ("right to explanation") check | ETH5 template exists but GDPR Art. 22 compliance is never evaluated or labeled | No specific Art. 22 output |
| **HIPAA** de-identification check | Not referenced anywhere in the codebase | Completely absent |

---

### Dashboard / UX Gaps

| Research Claims | Reality | Gap |
|---|---|---|
| "Visualizes validation **history**, real-time monitoring" (Section 6.2) | Validation history list in ProjectDetailPage but no charts | No visual history graph |
| **Comparison view** between two validation runs | Not present | Can't diff run A vs run B |

---

## Phased Implementation Plan

---

### Phase 1 — Quick Wins (1–2 days each, high research alignment)

These are small, well-scoped items that directly close stated gaps with minimal risk.

| # | Item | What to Do |
|---|---|---|
| 1.1 | **Explanation Fidelity metric** | In `ExplainabilityEngine`, compute `1 − mean(|f(x) − g(x)|)` where `g(x)` is the LIME local approximation prediction and `f(x)` is the model prediction on the same sample. Add as a `TransparencyReport` field. Surface it in the validation result card. |
| 1.2 | **JSON export button** | Add a "Export JSON" button to the report viewer and validation results page. It simply triggers a browser download of the already-returned API JSON. |
| 1.3 | **Equal Opportunity Difference default threshold fix** | Change `DEFAULT_FAIRNESS_THRESHOLDS["equal_opportunity_difference"]` from `0.10` to `0.05` to match the research table. |
| 1.4 | **"Re-run same config" button** | On the validation results page, add a "Re-run" button that pre-populates the validation wizard with the same model, dataset, and configuration from the previous run (read from the suite record). |
| 1.5 | **LIME results delivered to frontend** | The `ExplainabilityEngine.explain_local_lime()` method exists but is never called in the transparency validation route. Call it for 5 sample rows and include the output in the transparency result response. |

---

### Phase 2 — Medium Effort (2–5 days each, important for completeness)

| # | Item | What to Do |
|---|---|---|
| 2.1 | **Excel & CSV Parquet dataset upload** | In `datasets.py`, add `.xlsx` and `.parquet` to `ALLOWED_DATASET_EXTENSIONS`. Use `pd.read_excel()` / `pd.read_parquet()` based on extension. Convert to CSV internally for storage. |
| 2.2 | **Increase file size limit to 500 MB** | Change `MAX_UPLOAD_SIZE_BYTES` in frontend and the `max_upload_size` setting in `config.py` from 100 MB → 500 MB (2 GB per research is excessive for a local tool but 500 MB is realistic). |
| 2.3 | **Validation history time-series chart** | Add a line/area chart (using Recharts or MUI X Charts) to the project detail page showing fairness metric values across validation runs over time. Backend already has `/validate/history/{project_id}` returning the data needed. |
| 2.4 | **Compliance certificate PDF** | Create a styled "certificate" PDF variant: project name, date, overall pass/fail, each principle scored, regulatory references. Differentiate it visually from the standard validation report. |
| 2.5 | **Regulatory compliance labels** | On the validation result card, after a fairness run: check whether Demographic Parity ≥ 0.80 and emit an explicit "ECOA 80% Rule: COMPLIANT / NON-COMPLIANT" label. Do the same for EEOC Four-Fifths (ETH4). These are just conditional labels over the already-computed metrics. |
| 2.6 | **Run comparison view** | Allow the user to select two past validation suites and see a side-by-side diff (metric values + pass/fail delta). Can be a modal or a dedicated `/projects/:id/compare` page. |

---

### Phase 3 — Complex / Longer Term (1–2 weeks each, advanced features)

| # | Item | What to Do |
|---|---|---|
| 3.1 | **Differential Privacy measurement** | Implement a `DifferentialPrivacyChecker` that: (a) measures current ε-sensitivity of the dataset, (b) optionally applies Laplace noise to quasi-identifier columns, (c) reports the resulting ε value and whether it satisfies a user-set budget. Add as an optional privacy check alongside k-anonymity / l-diversity. |
| 3.2 | **Periodic / scheduled re-validation** | Add a `ScheduledValidation` model and a Celery beat task. Let users set a schedule (daily/weekly/monthly) per project. When the cron fires, re-run the last successful validation config and compare results. Send an in-app notification or email if any metric regresses. |
| 3.3 | **In-app alerts on metric regression** | Build a notification system (in-app banner + optional email). Trigger when a re-run finds a metric that previously passed now failing. |
| 3.4 | **HIPAA de-identification check** | Add a `HIPAAChecker` to the privacy validator: checks for the 18 HIPAA identifiers (names, dates, geographic data below state level, phone/fax, SSN, etc.) as a named sub-check. Surface as "HIPAA Safe Harbor: PASS / FAIL". |
| 3.5 | **HTML report export** | Build an HTML report template (Jinja2) that mirrors the PDF layout but is browser-renderable. Add a `/reports/validation/{id}/html` endpoint and a download button. |
| 3.6 | **Guided remediation workflow** | When a validation fails a specific metric, present a structured remediation checklist (e.g., "Fairness failed → Step 1: Check sensitive feature correlation, Step 2: Apply reweighing, Step 3: Re-validate"). Each step is a card with "Mark done" and a link to documentation. This is the "Apply Fixes" step from the research user flow (Section 6.3 Step 7). |

---

## Summary Table

| Phase | Items | Effort | Research Alignment |
|---|---|---|---|
| Phase 1 — Quick Wins | 5 items | ~1–2 days each | Closes exact research metric / formula gaps |
| Phase 2 — Medium Effort | 6 items | ~2–5 days each | Closes format, chart, certificate, regulatory label gaps |
| Phase 3 — Complex | 6 items | ~1–2 weeks each | Closes monitoring, DP, HIPAA, remediation workflow gaps |

**Total: 17 identified gaps across 3 phases.**

The product is already strong — all four ethical pillars (Fairness, Transparency, Privacy, Accountability) compute real metrics, the template/requirement/traceability pipeline is complete, and reports exist. The gaps are mostly around (a) secondary data formats, (b) a handful of missing metric computations from the research table, (c) time-series monitoring, and (d) regulatory compliance labels. None of the core architecture needs to change.
