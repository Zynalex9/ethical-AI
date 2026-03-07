# EthicScan AI Validator — Implementation Phases

> **How to use this file:** Hand each phase to an AI model one at a time. Complete and verify all items in a phase before moving to the next. Each task includes a clear objective, what to change, and where to find it.

---

## Phase 1 — Quick Wins
**Goal:** Close exact metric/formula gaps stated in the research document. Low risk, high alignment.

---

### Task 1.1 — Explanation Fidelity Metric

**What:** The research defines an Explanation Fidelity score as `1 − mean(|f(x) − g(x)|)` where `f(x)` is the model's prediction and `g(x)` is the LIME local approximation's prediction on the same sample. This formula is in the research table but never implemented.

**Where to change:**
- `ExplainabilityEngine` class — add the computation after LIME local explanations are generated
- `TransparencyReport` data model — add an `explanation_fidelity: float` field
- Validation result card (frontend) — surface the new field as a labelled metric

**Acceptance criteria:**
- `explanation_fidelity` appears in the API response for any transparency validation
- Value is a float between 0 and 1
- Displayed on the frontend result card with a label

---

### Task 1.2 — JSON Export Button

**What:** The API already returns full JSON results, but there is no "Export JSON" button in the UI. Users cannot download the raw result data.

**Where to change:**
- Report viewer page (frontend) — add an "Export JSON" button
- Validation results page (frontend) — add the same button
- Button action: trigger `window.URL.createObjectURL(new Blob([JSON.stringify(data)]))` download in the browser — no backend change needed

**Acceptance criteria:**
- "Export JSON" button visible on the report viewer and validation results pages
- Clicking it downloads a `.json` file containing the full validation result
- File is named something like `validation-{id}-results.json`

---

### Task 1.3 — Equal Opportunity Difference Threshold Fix

**What:** The research table specifies the threshold for Equal Opportunity Difference should be `≤ 0.05`. The codebase currently defaults to `0.10`.

**Where to change:**
- `config.py` or wherever `DEFAULT_FAIRNESS_THRESHOLDS` is defined
- Change `"equal_opportunity_difference": 0.10` → `"equal_opportunity_difference": 0.05`

**Acceptance criteria:**
- Default threshold for `equal_opportunity_difference` is `0.05`
- Any existing tests that assert `0.10` are updated
- The change does not break other fairness threshold logic

---

### Task 1.4 — "Re-run Same Config" Button

**What:** After a validation completes, users must manually create a new validation from scratch to re-run it. There is no way to repeat the same configuration.

**Where to change:**
- Validation results page (frontend) — add a "Re-run" button
- On click: read the previous suite record (model, dataset, config) and pre-populate the validation wizard with those values
- No backend change needed if the suite record already stores the full configuration

**Acceptance criteria:**
- "Re-run" button appears on the validation results page
- Clicking it opens the validation wizard pre-filled with the same model, dataset, and settings
- User can adjust settings before submitting or submit as-is

---

### Task 1.5 — Wire LIME Results to Frontend

**What:** `ExplainabilityEngine.explain_local_lime()` exists and works, but it is never called in the transparency validation route. LIME outputs are absent from all API responses and never shown in the UI.

**Where to change:**
- Transparency validation route (backend) — call `explain_local_lime()` for a sample of 5 rows and include the output in the response payload
- Transparency result response schema — add a `lime_local_explanations` field (list of per-row feature importance dicts)
- Frontend result card — display LIME local explanations alongside existing SHAP output

**Acceptance criteria:**
- LIME results appear in the API response for transparency validations
- At least 5 sample rows have LIME explanations returned
- Frontend displays LIME feature importance values (table or bar chart) for those rows

---

---

## Phase 2 — Medium Effort
**Estimated effort:** 2–5 days per item  
**Goal:** Close data format, chart, certificate, and regulatory label gaps.

---

### Task 2.1 — Excel and Parquet Dataset Upload Support

**What:** The research states support for CSV, Excel, Parquet, and JSON datasets. Currently only CSV is accepted.

**Where to change:**
- `datasets.py` — add `.xlsx` and `.parquet` to `ALLOWED_DATASET_EXTENSIONS`
- File parsing logic — use `pd.read_excel()` for `.xlsx` and `pd.read_parquet()` for `.parquet` based on file extension
- After reading, convert to CSV internally for consistent downstream storage and processing
- Frontend upload component — update accepted file types to include `.xlsx` and `.parquet`

**Acceptance criteria:**
- `.xlsx` and `.parquet` files are accepted by the upload endpoint without errors
- Uploaded files are converted to CSV and processed identically to native CSV uploads
- Invalid file types still return a clear error message

---

### Task 2.2 — Increase File Size Limit to 500 MB

**What:** The research claims support for datasets up to 2 GB. The current hard limit is 100 MB (20× smaller). A realistic target for a local tool is 500 MB.

**Where to change:**
- `config.py` — change `max_upload_size` from `100 MB` → `500 MB`
- Frontend upload component — update the displayed limit and the client-side validation check
- Any middleware or reverse proxy config that enforces a body size limit

**Acceptance criteria:**
- Files up to 500 MB can be uploaded successfully
- The UI shows "500 MB" as the maximum size
- Files over 500 MB are rejected with a clear error message

---

### Task 2.3 — Validation History Time-Series Chart

**What:** The research describes visualizing fairness metric values over time across validation runs. The project detail page shows a history list but has no charts.

**Where to change:**
- Project detail page (frontend) — add a line or area chart below or alongside the validation history list
- Data source: the existing `/validate/history/{project_id}` endpoint already returns the data needed
- Chart library: use Recharts or MUI X Charts (whichever is already in the project)
- Chart should show at least: Demographic Parity Ratio, Equalized Odds, and Equal Opportunity Difference over time (x-axis = run date, y-axis = metric value)

**Acceptance criteria:**
- A time-series chart is visible on the project detail page
- Chart updates when new validations are completed
- Each fairness metric is a separate line/series with a legend
- Chart is empty (with a placeholder message) if fewer than 2 runs exist

---

### Task 2.4 — Compliance Certificate PDF

**What:** The current compliance report is a plain JSON object. The research implies a visually distinct, printable compliance certificate.

**Where to change:**
- PDF report generator (backend) — create a new certificate template separate from the standard validation report
- Certificate content: project name, date, overall PASS/FAIL, each ethical principle scored (Fairness / Privacy / Transparency / Accountability), list of regulatory references checked
- Add a new endpoint `/reports/validation/{id}/certificate` that returns the certificate PDF
- Frontend — add a "Download Certificate" button on the compliance report page

**Acceptance criteria:**
- Certificate PDF is visually distinct from the standard report (different layout/header)
- Certificate includes all four principle scores and a clear overall verdict
- Download button on the compliance report page triggers the correct endpoint
- Certificate is printable (no overlapping elements, proper page margins)

---

### Task 2.5 — ECOA and EEOC Compliance Labels

**What:** The ECOA 80% Rule and EEOC Four-Fifths Rule thresholds are present in ETH1 and ETH4 templates, but no explicit "COMPLIANT / NON-COMPLIANT" label is emitted in results.

**Where to change:**
- Fairness validation result logic (backend) — after computing Demographic Parity:
  - If template is ETH1: check `demographic_parity_ratio >= 0.80` → emit `"ecoa_80_rule": "COMPLIANT"` or `"NON-COMPLIANT"`
  - If template is ETH4: apply the same check → emit `"eeoc_four_fifths_rule": "COMPLIANT"` or `"NON-COMPLIANT"`
- Validation result card (frontend) — display these labels as coloured badges (green/red) when present in the response

**Acceptance criteria:**
- ETH1 validations include an `ecoa_80_rule` compliance label in the response
- ETH4 validations include an `eeoc_four_fifths_rule` compliance label in the response
- Labels are shown as coloured badges on the result card
- Label is absent (not shown) for templates where the rule does not apply

---

### Task 2.6 — Run Comparison View

**What:** Users cannot compare two past validation runs. There is no diff view to see how metrics changed between runs.

**Where to change:**
- Project detail page (frontend) — add checkboxes or a "Compare" action to the validation history list, allowing selection of exactly two runs
- Create a comparison view: either a modal or a new `/projects/:id/compare?a={runA}&b={runB}` page
- Comparison should show: side-by-side metric values for each principle, a delta column (change between runs), and a PASS/FAIL status for each

**Acceptance criteria:**
- User can select two runs from the validation history and trigger a comparison
- Comparison view shows all metrics side-by-side with delta values
- Improved metrics shown in green, regressed metrics shown in red
- Comparison works for any two runs in the same project

---

---

## Phase 3 — Complex Features
**Estimated effort:** 1–2 weeks per item  
**Goal:** Close monitoring, differential privacy, HIPAA, and remediation workflow gaps.

---

### Task 3.1 — Differential Privacy Measurement

**What:** Differential Privacy is mentioned in the codebase only as a text recommendation. No actual ε measurement, noise application, or DP metric is computed.

**What to build:**
- New `DifferentialPrivacyChecker` class in the privacy validation module
- Functionality:
  1. Measure current ε-sensitivity of the dataset (based on quasi-identifier columns)
  2. Optionally apply Laplace noise to quasi-identifier columns to achieve a target ε budget
  3. Report the resulting ε value and whether it satisfies the user-set budget
- Add `differential_privacy` as an optional check in the privacy validation pipeline alongside k-anonymity and l-diversity
- Frontend — show ε value and budget compliance status on the privacy result card

**Acceptance criteria:**
- DP check runs when enabled and returns a measured ε value
- Noise application (when selected) modifies a copy of the data and reports the new ε
- Result includes a clear "DP Budget: SATISFIED / EXCEEDED" label
- DP check is opt-in (existing validations unaffected if not enabled)

---

### Task 3.2 — Periodic / Scheduled Re-Validation

**What:** There is no mechanism to automatically re-run validations on a schedule. The research describes continuous post-deployment monitoring.

**What to build:**
- New `ScheduledValidation` database model: stores project ID, last successful validation config, schedule (daily / weekly / monthly), enabled flag, last run timestamp
- Celery beat task that fires on the configured schedule, re-runs the last successful validation config, and stores the result as a new validation suite entry
- Settings UI — allow users to enable scheduling and pick a frequency per project
- On completion: trigger the in-app notification system (see Task 3.3)

**Acceptance criteria:**
- Users can enable a schedule for any project from the project settings page
- Celery beat fires the task at the correct interval
- Scheduled runs appear in the validation history list tagged as "Scheduled"
- Disabling the schedule stops future runs

---

### Task 3.3 — In-App Alerts on Metric Regression

**What:** When a re-run (scheduled or manual) finds a metric that previously passed now failing, there is no alert mechanism.

**What to build:**
- Notification model: stores user ID, project ID, message, severity, read status, timestamp
- Trigger logic: after any validation completes, compare results to the previous run; if any metric changed from PASS to FAIL, create a notification
- In-app notification banner or bell icon in the navigation — shows unread count, lists recent alerts
- Optional: email notification (configurable per user in profile settings)

**Acceptance criteria:**
- A notification is created when a metric regresses from PASS to FAIL
- Unread notifications are visible in the navigation
- Clicking a notification links to the relevant validation result
- Users can mark notifications as read
- Email notifications are optional and controlled per user

---

### Task 3.4 — HIPAA De-Identification Check

**What:** HIPAA is not referenced anywhere in the codebase. The research implies it should be supported as a privacy check.

**What to build:**
- New `HIPAAChecker` class in the privacy validation module
- Checks for the 18 HIPAA Safe Harbor identifiers: names, dates (except year), geographic data below state level, phone/fax numbers, email addresses, SSN, medical record numbers, health plan numbers, account numbers, certificate/license numbers, VINs, device identifiers, URLs, IP addresses, biometric identifiers, full-face photos, and any unique identifying numbers
- Each identifier type is a named sub-check with PASS/FAIL status
- Overall result: "HIPAA Safe Harbor: PASS / FAIL"
- Add as an optional privacy check; surface in privacy result card

**Acceptance criteria:**
- HIPAA check runs when enabled and tests all 18 identifier categories
- Each category shows individual PASS/FAIL in the result
- Overall "HIPAA Safe Harbor" label is shown on the privacy result card
- Check is opt-in (existing validations unaffected if not enabled)

---

### Task 3.5 — HTML Report Export

**What:** The system only exports PDF reports. The research specifies HTML report export as well.

**What to build:**
- Jinja2 HTML report template that mirrors the structure and content of the PDF report
- New endpoint `/reports/validation/{id}/html` that renders and returns the HTML file
- Frontend — add "Export HTML" button alongside the existing "Export PDF" button on the report page

**Acceptance criteria:**
- HTML report is browser-renderable without additional dependencies
- Content matches the PDF report (same sections, metrics, and narrative)
- Download button returns an `.html` file that opens correctly in a browser
- Report is print-friendly (usable via browser print dialog as an alternative to PDF)

---

### Task 3.6 — Guided Remediation Workflow

**What:** When a validation fails, users receive metric scores but no actionable guidance. The research describes a structured "Apply Fixes → Retest" workflow (Section 6.3 Step 7).

**What to build:**
- Remediation checklist system: for each failing metric, show a structured list of remediation steps
  - Example for Fairness failure: "Step 1 — Check sensitive feature correlation → Step 2 — Apply reweighing → Step 3 — Re-validate"
- Each step is a card with: description, "Mark as done" checkbox, and a link to documentation
- Checklist is shown on the validation results page when one or more metrics fail
- "Re-validate" step uses the re-run config button (Task 1.4) to re-submit

**Acceptance criteria:**
- Remediation checklist appears automatically when any metric fails
- Each failing principle (Fairness / Privacy / Transparency / Accountability) has its own set of steps
- Users can mark steps as done; progress is saved (per validation run, per user)
- Completing all steps and clicking "Re-validate" pre-fills the validation wizard

---

---

## Summary

| Phase | Tasks | Effort per Task | Primary Gap Closed |
|---|---|---|---|
| Phase 1 — Quick Wins | 5 | 1–2 days | Missing metric formulas, threshold values, missing UI actions |
| Phase 2 — Medium Effort | 6 | 2–5 days | Data formats, history charts, certificate PDF, regulatory labels, run comparison |
| Phase 3 — Complex | 6 | 1–2 weeks | DP measurement, scheduled monitoring, alerts, HIPAA, HTML export, remediation |

**Total: 17 tasks across 3 phases.**

> Complete Phase 1 entirely before starting Phase 2. Phase 3 tasks are mostly independent of each other and can be prioritised individually based on user demand.

---

---

## Phase 4 — Bug Fixes & UI Issues (Discovered March 2026)

> These are active bugs and UX defects found during testing. Fix these before demoing the system.

---

### Task 4.1 — Fairness Radar Chart Is Meaningless / Wrong Scale

**What:** The Fairness Radar chart shown after validation displays values that are not normalised to the 0–1 range expected by a radar chart. The axis labels show values like 0–4 instead of 0–1, making the chart visually misleading. All fairness metrics (demographic parity ratio, equalized odds ratio, disparate impact ratio, equalized odds difference, demographic parity difference) are already 0–1 values or close to it — the chart renderer is not setting the domain correctly.

**Where to change:**
- Frontend validation results page — find the `RadarChart` component and its data mapping
- Clamp/normalise each metric value to [0, 1] before passing to the chart (ratio metrics are already 0–1; difference metrics should be clamped to [0, 1])
- Set the `PolarRadiusAxis` domain to `[0, 1]` explicitly
- Add threshold rings (e.g. a dashed ring at 0.8) so the user can see pass/fail at a glance

**Acceptance criteria:**
- Radar chart axis always shows 0–1
- Each metric value maps correctly to the radar arm
- A threshold ring or reference value is visible

---

### Task 4.2 — Confusion Matrix by Group Is Empty

**What:** The "Confusion Matrix by Group" table is rendered with no rows even after a completed fairness validation. The table shows only the header row (Group | TP | FP | TN | FN) and nothing else.

**Root cause to investigate:**
- The `by_group` field in `ValidationResult.details` may not be storing confusion matrix data
- Or the frontend component is looking for a field name that doesn't match what the backend sends (e.g. `confusion_matrix` vs `by_group_confusion_matrix`)
- Check `_run_fairness_validation_async` in `validation_tasks.py` — confirm the confusion matrix per group is computed and saved in `details`
- Check the frontend component that renders this table — confirm the field path it reads from

**Where to change:**
- Backend `validation_tasks.py` — ensure per-group TP/FP/TN/FN is computed and stored in `ValidationResult.details`
- Frontend fairness result card — fix the field path so it reads the correct key from the API response

**Acceptance criteria:**
- After a fairness validation each demographic group appears as a row in the table
- TP, FP, TN, FN values are populated for each group
- Empty state message shown only when the data is genuinely absent

---

### Task 4.3 — k-Anonymity Group Distribution Chart Is Empty

**What:** The "k-Anonymity Group Distribution" chart renders as an empty white box even after a successful privacy validation. No bars or data points appear.

**Root cause to investigate:**
- The privacy validator likely computes k-anonymity group sizes but the distribution data is not included in the API response, or is nested under a different key than what the frontend chart reads
- Check `_run_privacy_validation_async` — confirm `group_distribution` or equivalent data is in the response
- Check the frontend privacy result card — confirm the chart reads the correct field

**Where to change:**
- Backend privacy task — include per-group quasi-identifier equivalence class sizes in the result payload
- Frontend chart component — read the correct field and pass it to the chart

**Acceptance criteria:**
- Chart shows a bar per equivalence class size (or bucketed histogram)
- Chart is non-empty after any successful privacy validation that computed k-anonymity
- Empty state shown only when k-anonymity was not selected

---

### Task 4.4 — Privacy Risk Score Is Always 20%

**What:** The Privacy Risk Score gauge always shows 20% (Low Risk) regardless of the actual validation results. It is not dynamically computed from the privacy check outcomes.

**Root cause to investigate:**
- The risk score calculation is likely hard-coded or using a default value
- Check the backend privacy task for where `privacy_risk_score` is computed
- Check the frontend gauge component for whether it reads from the API or uses a static value

**Where to change:**
- Backend — compute the risk score based on: how many privacy checks failed, k value (lower = higher risk), l-diversity result, DP epsilon value if computed
- A simple formula: `risk_score = (failed_checks / total_checks) * 100` is sufficient
- Frontend — read the dynamic score from the API response

**Acceptance criteria:**
- Risk score changes based on actual check results
- 0 failures → low risk (≤ 30%)
- Partial failures → medium risk (30–70%)
- Most/all failures → high risk (> 70%)
- Score is computed server-side and returned in the API response

---

### Task 4.5 — PDF Report Is Unreadable (Letters Stacked / Overlapping)

**What:** When exporting a validation report or compliance certificate to PDF, all text is rendered as a single column where letters and lines are stacked on top of each other, making the document completely unreadable.

**Root cause:** The PDF generator (likely `reportlab` or `weasyprint`) has a layout/encoding issue — either the font is not embedded, the page width is not set correctly, or HTML → PDF conversion is failing to apply CSS layout rules.

**Where to change:**
- Backend PDF generator (`reports` service or router) — identify which library is used
- If using `reportlab`: ensure `SimpleDocTemplate` page size is set to `A4` or `letter`, text is wrapped in `Paragraph` with a `SimpleDocStyle`, and multi-column layouts use `Table` with proper column widths
- If using `weasyprint`/`pdfkit`: ensure the HTML template has explicit `width`, `font-family`, and `page` CSS rules; avoid using flexbox/grid for print layouts
- Test by generating a report and opening the PDF in a viewer

**Acceptance criteria:**
- PDF opens cleanly with readable text
- Sections for Fairness, Transparency, Privacy, Accountability each occupy their own visual area
- No overlapping text or truncated content
- Certificate PDF has a professional layout (header, sections, signature area, page number)

---

### Task 4.6 — "Scheduled Re-Validation" Section Needs Explanation & Current Status

**What:** The Validations tab shows a "Scheduled Re-Validation" card with three buttons (Enable daily / Enable weekly / Enable monthly) but no explanation of what this does, no indication of whether a schedule is currently active, and no way to disable an existing schedule.

**Where to change:**
- Frontend `ScheduleSettings` component — add:
  - A short description: "Automatically re-run the latest validation configuration on a regular schedule to detect model drift and regressions."
  - Show current schedule status: "No schedule active" OR "Running weekly — next run: [date]"
  - Add a "Disable" button that appears when a schedule is active
  - Show the last scheduled run date and result (pass/fail)

**Acceptance criteria:**
- User can tell at a glance whether a schedule is active and when it last ran
- "Disable" button cancels the schedule
- Description text explains the feature in plain language

---

### Task 4.7 — Audit Log Page Is Empty (Shows No Records)

**What:** The Audit Log page shows the correct table structure (Date | Action | Resource | User ID | Details) with pagination showing "1–25 of more than 25" but no rows are rendered. The data exists in the database (`audit_logs` table) but is not displayed.

**Root cause to investigate:**
- The frontend audit log component likely calls the API and gets data back, but maps the wrong field names
- Or the backend returns records but uses `user_id` as a UUID and the frontend tries to render it as a name
- Check the audit log API endpoint response shape and compare to what the frontend table expects

**Where to change:**
- Frontend Audit Log page/component — fix field name mappings so rows actually render
- Ensure `action`, `resource_type`, `resource_id`, `created_at`, and `details` all map to the correct table cells
- Format `user_id` as the user's email or name if possible (join on users table in the backend), otherwise display the truncated UUID

**Acceptance criteria:**
- Audit log rows are visible after page load
- Each row shows: date/time, action type, resource type + truncated ID, user identifier, and a summary of details
- Pagination works correctly

---

### Task 4.8 — Fairness Validation Detail Page With Metric Explanations

**What:** After a fairness validation completes, users see metric names and pass/fail chips but no explanation of what each metric means, why it passed or failed, or what to do about it. There is no dedicated detail page for fairness results.

**What to build:**
- A dedicated Fairness Detail view (modal or expanded section within the validation results page)
- For each metric, show:
  - **Metric name** with a plain-English definition (e.g. "Demographic Parity Ratio — measures whether positive prediction rates are equal across demographic groups")
  - **Your value** vs **threshold** (e.g. "0.72 vs required ≥ 0.80")
  - **Status**: Pass ✓ or Fail ✗ with a coloured badge
  - **Why it failed** (if applicable): e.g. "Group 'Female' received positive predictions 28% less often than group 'Male'"
  - **What to do**: a brief 1–2 sentence remediation hint (e.g. "Consider reweighing training data or applying post-processing equalisation")
- Per-group breakdown table already exists but should be linked from this detail view
- Add a "View Details" button on the metric rows in the results card to open this view

**Metric definitions to include:**
| Metric | Definition | Threshold | Fail Meaning |
|---|---|---|---|
| Demographic Parity Ratio | Ratio of positive prediction rates between groups | ≥ 0.80 | One group gets fewer positive predictions proportionally |
| Equalized Odds Ratio | Ratio of true positive AND false positive rates across groups | ≥ 0.80 | Model is more accurate for one group than another |
| Disparate Impact Ratio | Ratio of selection rates — ECOA/EEOC 80% rule | ≥ 0.80 | Adverse impact on protected group under employment law |
| Equalized Odds Difference | Absolute difference in TPR/FPR across groups | ≤ 0.10 | Unequal error rates between groups |
| Demographic Parity Difference | Absolute difference in positive prediction rates | ≤ 0.10 | Unequal selection rates between groups |

**Where to change:**
- Frontend: add a `FairnessMetricDetail` component (modal or expandable section)
- Embed metric definitions as a static lookup table in the component (no backend change needed for definitions)
- The per-group data already comes from the API — wire it to this component

**Acceptance criteria:**
- Each metric in the fairness results card has a "?" or "Details" button
- Clicking it shows the metric definition, current value, threshold, pass/fail reason, and a remediation hint
- Per-group breakdown is accessible from this view
- Works for both passed and failed metrics

---

### Task 4.9 — LIME/SHAP Feature Contribution Chart Shows All Zeros

**What:** The LIME explanations section shows bars for features like `feature_0`, `feature_1`, etc. all with value `0.000` and `shap_contribution: 0`. The explanation fidelity shows 100% which is suspicious — it means the local model perfectly matches predictions of 0 contributions, suggesting the model is either constant or the feature extraction is wrong.

**Root cause to investigate:**
- The dummy model or the uploaded model may be predicting the same class for all inputs (constant predictor), which causes all SHAP/LIME contributions to be zero
- Or the feature names extracted from the dataset are not the same features the model was trained on (mismatch in column names or encodings)
- Check `ExplainabilityEngine` — confirm it is passing the correct feature-aligned `X` to LIME/SHAP
- Check whether the dummy model in `examples/dummy_model.py` actually returns varying predictions

**Where to change:**
- Backend `explainability_engine.py` — add a check: if all SHAP/LIME values are zero, log a warning and include a `"warning": "All contributions are zero — model may be constant or feature mismatch detected"` in the response
- Frontend — show this warning prominently if present instead of silently rendering zero bars
- Documentation hint: instruct users to upload a properly trained model with varying predictions

**Acceptance criteria:**
- If all contributions are zero, a visible warning is shown in the UI
- The warning explains the likely cause in plain language
- For a model with real varying predictions, SHAP/LIME contributions are non-zero

---

## Summary

| Phase | Tasks | Effort per Task | Primary Gap Closed |
|---|---|---|---|
| Phase 1 — Quick Wins | 5 | 1–2 days | Missing metric formulas, threshold values, missing UI actions |
| Phase 2 — Medium Effort | 6 | 2–5 days | Data formats, history charts, certificate PDF, regulatory labels, run comparison |
| Phase 3 — Complex | 6 | 1–2 weeks | DP measurement, scheduled monitoring, alerts, HIPAA, HTML export, remediation |
| Phase 4 — Bug Fixes & UI Issues | 9 | 0.5–2 days | Charts empty/wrong, PDF broken, audit log invisible, missing detail pages |

**Total: 26 tasks across 4 phases.**

> Complete Phase 1 entirely before starting Phase 2. Phase 3 tasks are mostly independent of each other and can be prioritised individually based on user demand. Phase 4 bugs should be fixed in parallel with or before any Phase 2/3 work since they affect demo-ability.