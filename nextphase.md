# Next Phase — Feature Roadmap

---

## Feasibility Analysis

### Q1: Can users define custom fairness rules beyond the 6 hardcoded metrics?

**Yes — fully feasible.** The architecture already supports it:

- `FairnessValidator.validate_all()` accepts `selected_metrics: List[str]` and `thresholds: Dict[str, float]`, and dispatches via a `metric_runners` dict (line 595–602 in `fairness_validator.py`).
- The frontend `ValidationPage.tsx` already lets users pick which metrics to run and override thresholds per metric (lines 150–196, 461–468).
- The `Requirement` model has a `specification: JSONB` column that stores arbitrary rule configs.

**What's missing?** The 6 metric keys are hardcoded in `metric_runners`. To let users define *custom* fairness rules, we need:
1. A way for users to define a new rule as: **"compute metric X on column Y, compare using operator Z against threshold T"** — where X can be any sklearn/custom function (e.g., `accuracy_score`, `precision_score`, group-ratio of any column).
2. A backend registry that maps user-defined metric names to their computation logic.
3. Frontend UI for creating/saving/reusing these rules.

**Recommended approach:** Expression-based custom rules. The user defines rules like:
- *"max group difference in `precision_score` ≤ 0.15"*
- *"min group ratio of `recall_score` ≥ 0.75"*

These use sklearn metrics as building blocks — no arbitrary code execution needed, so it's safe and bounded.

---

### Q2: Can users define custom privacy rules?

**Yes — also feasible.** Current privacy checks (`pii_detection`, `k_anonymity`, `l_diversity`, `differential_privacy`, `hipaa`) are dispatched via a requirements dict in `PrivacyValidator.validate()`. The frontend already lets users toggle checks and set `k`, `l`, and `ε` parameters.

**What's missing?** Users can't add entirely new privacy checks, but they can get practical customization through:
1. **Custom PII patterns** — users add their own regex patterns or column-name keywords (e.g., `"employee_id"`, `"patient_mrn"`).
2. **Custom k/l per column group** — different quasi-identifier sets with different k values.
3. **Column-level sensitivity tagging** — mark which columns are "sensitive", "quasi-identifier", "safe" before running.

**NOT recommended:** Letting users write arbitrary Python validators — too risky, too complex, out of scope.

---

## Feature Roadmap (Prioritized)

> Scope rule: Every feature below is a concrete user-facing capability that directly improves the core workflow. No infrastructure-only tasks, no premature optimization.

---

### Feature 1: Custom Fairness Rules

**Goal:** Users can create reusable fairness rules beyond the 6 defaults and apply them during validation.

#### Task 1.1 — Backend: Custom metric registry
**Files:** `backend/app/validators/fairness_validator.py`

- Add a `CUSTOM_METRIC_REGISTRY` dict that maps user-defined metric names to callables.
- Each custom metric is defined as:
  ```python
  {
      "name": "min_precision_ratio",
      "base_metric": "precision_score",    # from sklearn.metrics
      "aggregation": "min_ratio",          # min(group) / max(group)
      "comparison": ">=",                  # >= or <=
      "default_threshold": 0.8
  }
  ```
- Add a `run_custom_metric()` method that uses `MetricFrame` with any sklearn metric as the scorer, then applies the aggregation (ratio or difference) and compares to threshold.
- Wire custom metrics into `validate_all()` alongside builtin metrics.

#### Task 1.2 — Backend: API for CRUD on custom rules
**Files:** New file `backend/app/routers/custom_rules.py`, modify `backend/app/models/` (new `CustomRule` model or extend `Requirement.specification`)

- `POST /api/v1/custom-rules` — create a custom fairness or privacy rule (stored per project).
- `GET /api/v1/custom-rules?project_id=...` — list rules for a project.
- `PUT /api/v1/custom-rules/{id}` — update a rule.
- `DELETE /api/v1/custom-rules/{id}` — delete a rule.
- Schema: `{ name, principle, base_metric, aggregation, comparison, default_threshold, description }`.

#### Task 1.3 — Backend: Integrate custom rules into validation pipeline
**Files:** `backend/app/tasks/validation_tasks.py`, `backend/app/routers/validation.py`

- When a validation suite is submitted, also fetch any custom rules linked to the project.
- Pass custom rule definitions to `FairnessValidator.validate_all()` alongside the built-in `selected_metrics`.
- Store results using the same `ValidationResult` model (they already support arbitrary `metric_name` strings).

#### Task 1.4 — Frontend: Custom rules creation UI
**Files:** New component `frontend/src/components/CustomRuleEditor.tsx`, modify `frontend/src/pages/ValidationPage.tsx`

- Add a "Custom Rules" section in the fairness config step of the validation wizard.
- UI form: name, base metric (dropdown of supported sklearn metrics), aggregation type (min_ratio / max_difference), comparison (≥ / ≤), threshold (number input).
- Show existing custom rules as chips; each can be toggled on/off for the current run.
- "Save Rule" persists via the API; rules are reusable across validation runs.

#### Task 1.5 — Frontend: Display custom rule results
**Files:** `frontend/src/pages/ValidationPage.tsx`

- Custom metrics appear in the results section alongside built-in metrics.
- Same pass/fail chip, same group-level breakdown display.
- No new result page needed — current result rendering already handles arbitrary `metric_name` keys.

---

### Feature 2: Custom Privacy Rules (PII Patterns & Multi-Config)

**Goal:** Users can add their own PII detection patterns and define multiple k-anonymity/l-diversity configurations.

#### Task 2.1 — Backend: User-defined PII patterns
**Files:** `backend/app/validators/privacy_validator.py`

- Accept an optional `custom_pii_patterns: Dict[str, str]` parameter in `detect_pii()`.
- The dict maps pattern names to regex strings, e.g., `{"employee_id": r"\bEMP-\d{6}\b"}`.
- Merge user patterns with the built-in `COMPILED_PII_PATTERNS` at runtime.
- Also accept `custom_pii_column_names: Set[str]` to extend the `PII_COLUMN_NAMES` set.

#### Task 2.2 — Backend: Multiple k-anonymity configurations
**Files:** `backend/app/validators/privacy_validator.py`, `backend/app/routers/validation.py`

- Allow `k_anonymity` to accept a list of configs instead of a single config:
  ```json
  [
    { "quasi_identifiers": ["age", "zip"], "k": 5 },
    { "quasi_identifiers": ["age", "zip", "gender"], "k": 3 }
  ]
  ```
- Run each configuration separately and report per-config results.
- Update `PrivacyValidationRequest` schema to accept `k_anonymity_configs: List[KConfig]`.

#### Task 2.3 — Frontend: PII pattern editor
**Files:** New component `frontend/src/components/PiiPatternEditor.tsx`, modify privacy config section in `ValidationPage.tsx`

- Small form: pattern name + regex string + test value.
- Show existing custom patterns as editable rows.
- Pass to the API as `custom_pii_patterns`.

#### Task 2.4 — Frontend: Multi-config k-anonymity UI
**Files:** Modify privacy config in `ValidationPage.tsx`

- Instead of a single `k` input, allow "Add another config" button.
- Each config row: select quasi-identifiers + set k value.
- Results section shows per-config pass/fail.

---

### Feature 3: Validation Comparison (Run-over-Run)

**Goal:** Users can compare results from two validation runs side by side to see if a model improved or degraded.

#### Task 3.1 — Backend: Comparison endpoint
**Files:** New endpoint in `backend/app/routers/validation.py`

- `GET /api/v1/validations/compare?suite_a={id}&suite_b={id}` — returns a diff object:
  ```json
  {
    "fairness": {
      "demographic_parity_ratio": { "run_a": 0.82, "run_b": 0.91, "delta": +0.09, "improved": true }
    },
    ...
  }
  ```
- Query `ValidationResult` for both suites and compute deltas.

#### Task 3.2 — Frontend: Comparison view
**Files:** New component `frontend/src/components/ValidationComparison.tsx`, modify `ValidationPage.tsx`

- Add "Compare with previous run" button in results step.
- Side-by-side cards showing metric deltas with ↑/↓ arrows and color coding (green = improved, red = degraded).
- Reuse existing metric display components.

---

### Feature 4: Dataset Column Profiling

**Goal:** Before running validations, show users a data profile of their dataset (distribution stats, missing values, cardinality) so they can pick better quasi-identifiers and sensitive features.

#### Task 4.1 — Backend: Column profiling endpoint
**Files:** New endpoint in `backend/app/routers/datasets.py`

- `GET /api/v1/datasets/{id}/profile` — for each column return:
  - `dtype`, `unique_count`, `null_count`, `null_percentage`
  - For numeric: `min`, `max`, `mean`, `median`, `std`
  - For categorical: top 10 value counts
- Compute via pandas on the loaded CSV (cap at first 10k rows for performance).

#### Task 4.2 — Frontend: Profile display
**Files:** New component `frontend/src/components/DatasetProfile.tsx`, surface in `ProjectDetailPage.tsx`

- Render a table with column stats.
- Highlight potentially sensitive columns (high cardinality, string type) with a warning badge.
- Users can click a column to mark it as "quasi-identifier" or "sensitive" — pre-populates the validation config.

---

### Feature 5: Validation Presets (Save & Reuse Configurations)

**Goal:** Users can save a complete validation configuration (which validators, which metrics, thresholds, column selections) as a named preset and re-apply it in one click.

#### Task 5.1 — Backend: Preset CRUD
**Files:** New model `backend/app/models/validation_preset.py`, new router `backend/app/routers/presets.py`

- Model: `id`, `project_id`, `name`, `config: JSONB` (stores entire validation config), `created_by`, `created_at`.
- CRUD endpoints: `POST / GET / PUT / DELETE /api/v1/presets`.

#### Task 5.2 — Frontend: Save/Load preset UI
**Files:** Modify `ValidationPage.tsx`

- "Save as Preset" button after configuring a run → opens name dialog → saves via API.
- "Load Preset" dropdown at the top of the wizard → populates all form fields from saved config.
- This is different from templates (which are domain-level defaults). Presets are user-specific saved configs.

---

### Feature 6: Export Validation Results (CSV / JSON)

**Goal:** Users can download validation results in machine-readable format for integration with external tools.

#### Task 6.1 — Backend: Export endpoint
**Files:** Modify `backend/app/routers/reports.py`

- `GET /api/v1/reports/{suite_id}/export?format=csv` — returns a CSV with one row per metric (metric_name, value, threshold, passed, group breakdown).
- `GET /api/v1/reports/{suite_id}/export?format=json` — returns structured JSON of all results.
- Leverage existing `ValidationResult` queries.

#### Task 6.2 — Frontend: Export buttons
**Files:** Modify results section in `ValidationPage.tsx`

- Add "Export CSV" and "Export JSON" buttons next to the existing "Download PDF" button.
- Simple download trigger via axios blob request.

---

## Summary Table

| # | Feature | Effort | Priority | Backend | Frontend |
|---|---|---|---|---|---|
| 1 | Custom Fairness Rules | Medium | High | 3 tasks | 2 tasks |
| 2 | Custom Privacy Rules | Small–Medium | High | 2 tasks | 2 tasks |
| 3 | Validation Comparison | Small | Medium | 1 task | 1 task |
| 4 | Dataset Column Profiling | Small | Medium | 1 task | 1 task |
| 5 | Validation Presets | Small | Medium | 1 task | 1 task |
| 6 | Export Results (CSV/JSON) | Small | Low | 1 task | 1 task |

**Recommended implementation order:** 1 → 2 → 4 → 3 → 5 → 6

Features 1 and 2 directly address the user's core question about custom rules. Feature 4 helps users make better decisions when configuring validations. Features 3, 5, and 6 are quality-of-life improvements.
