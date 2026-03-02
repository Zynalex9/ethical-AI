# User Guide — Ethical AI Requirements Engineering Platform

> This guide is written for **non-technical users** (auditors, compliance officers, project managers) who need to validate AI models against ethical standards.

---

## 1. Key Concepts

| Term | Plain English | Why It Matters |
|------|---------------|----------------|
| **Fairness** | The model treats every demographic group (gender, race, age…) equally. | Prevents discrimination — legally required in lending, hiring, healthcare. |
| **Demographic Parity** | Each group should be selected/approved at roughly the same rate. | The "80 % rule" means minority selection rate ≥ 80 % of majority rate. |
| **Equal Opportunity** | The model predicts correctly for each group at the same rate. | A medical test should have the same true-positive rate for everyone. |
| **Disparate Impact** | Ratio of favourable-outcome rates between groups. | If < 0.80 → evidence of adverse impact. |
| **Transparency** | You can understand *why* the model made a specific decision. | Key for trust, debugging, and legal "right to explanation" (GDPR Art. 22). |
| **SHAP** | Measures how much each input feature contributes to a prediction. | Shows which columns (income, age…) pushed the model toward "approve" or "deny". |
| **LIME** | Same idea as SHAP, but uses a simpler local approximation. | Good for quick "which features mattered most?" explanations. |
| **Privacy** | Personal data is protected against re-identification. | PII exposure or weak anonymisation can violate GDPR / HIPAA. |
| **PII Detection** | Scanning dataset columns for personally identifying information. | Names, emails, SSNs should be redacted before model training. |
| **k-Anonymity** | Every row in the dataset is indistinguishable from at least *k − 1* other rows on quasi-identifiers. | Higher *k* → harder to single out an individual. |
| **l-Diversity** | Within each k-anonymous group, the sensitive attribute has at least *l* distinct values. | Prevents "everyone in this group has diabetes" inference attacks. |
| **Accountability** | Every action (model upload, validation run, result) is logged with who/when/what. | Audit trail for regulators and internal reviews. |

---

## 2. Getting Started

### Step 1 — Create an Account

1. Open the platform (default: http://localhost:5173).
2. Click **Register** → enter your name, email, password.
3. You are logged in automatically.

### Step 2 — Create a Project

1. Go to **Projects** in the sidebar.
2. Click **New Project**.
3. Choose **Start from scratch** (name + description) or **Start from template** (pre-configured ethical rules for your industry).
4. Click **Create**.

### Step 3 — Upload a Model

1. Open your project.
2. Go to the **Models** tab → **Upload Model**.
3. Supported formats: `.pkl`, `.joblib`, `.h5`, `.keras`, `.pt`, `.pth`, `.onnx`.
4. Max size: 100 MB.

### Step 4 — Upload or Load a Dataset

1. Go to the **Datasets** tab.
2. Upload a **CSV** file, or click **Load Benchmark Dataset** to use a preset (COMPAS, Adult Income, German Credit).
3. Select the **target column** (the column the model predicts).
4. Select any **sensitive attributes** (e.g. gender, race).

### Step 5 — Generate Ethical Requirements

1. From your project, click **Elicit Requirements**.
2. Under **Dataset Analysis**, select a dataset and click **Analyze**.
3. The system auto-detects PII, class imbalance, and proxy variables, then suggests requirements.
4. **Accept** or **Reject** each suggestion, then they appear in your project.
5. Optionally, click **Add Manual Requirement** to write your own.

### Step 6 — Run a Validation

1. From your project, click **Run Validation**.
2. **Step 1** — Select validators: Fairness, Transparency, Privacy.
3. Optionally choose a **template preset** (e.g. ETH1: Financial Services) to auto-configure metrics and thresholds.
4. **Step 2** — Choose model, dataset, configure metrics/thresholds if needed.
5. **Step 3** — Link requirements (optional but recommended).
6. Click **Run All Validations**. Progress bar shows real-time status.
7. **Step 4** — View results: each principle shows PASS / FAIL with detailed metrics.

### Step 7 — View Reports & Traceability

- **Report Viewer** — Navigate to a validation suite report for executive summary, charts, and recommendations.
- **Traceability Matrix** — See which requirements → datasets → models → validations are connected.
- **Root-Cause Analysis** — For any failed validation, click to see what went wrong and recommended actions.
- **PDF Export** — Download a compliance report as PDF for regulators or internal review.

---

## 3. Understanding Validation Results

### Fairness Results

| Metric | What "PASS" means | Typical threshold |
|--------|--------------------|----|
| Demographic Parity Ratio | All groups get approved at similar rates | ≥ 0.80 |
| Equal Opportunity Difference | True positive rates are similar across groups | ≤ 0.10 |
| Equalized Odds Difference | Both TPR and FPR are similar | ≤ 0.10 |
| Disparate Impact Ratio | Favorable outcome ratio ≥ threshold | ≥ 0.80 |

### Transparency Results

- **Feature Importance** — Bar chart showing which features (columns) the model relies on most.
- **Sample Predictions** — For individual predictions, a breakdown of how each feature pushed the outcome.
- **Model Card** — Summary of model type, performance metrics, intended use.

### Privacy Results

- **PII Detection** — Table listing columns that look like personal data (match: 0 PII columns = PASS).
- **k-Anonymity** — Shows whether every quasi-identifier group has at least *k* members.
- **l-Diversity** — Shows whether sensitive attributes are diverse within each group.

---

## 4. Templates & Industry Standards

| Template | Domain | Key Rules |
|----------|--------|-----------|
| GEN-FAIRNESS | General | Demographic Parity ≥ 0.80, Equal Opportunity ≤ 0.10 |
| GEN-TRANSPARENCY | General | SHAP feature importance, model card |
| GEN-PRIVACY | General | PII detection, k-anonymity ≥ 5 |
| ETH1 | Finance | 80 % rule (ECOA), Disparate Impact ≥ 0.80 |
| ETH2 | Healthcare | Equal Opportunity ≤ 0.03, SHAP 100 % coverage |
| ETH3 | Criminal Justice | Equalized Odds ≥ 0.85, audit trail required |
| ETH4 | Employment | Four-Fifths Rule, no PII in features |
| ETH5 | GDPR (EU) | Right to explanation, k-anonymity ≥ 5, no PII |
| ETH6 | Education | Demographic Parity ≥ 0.75, explanation for rejections |

---

## 5. FAQ

**Q: What file formats are supported for models?**
A: sklearn pickle (`.pkl`, `.joblib`), TensorFlow (`.h5`, `.keras`), PyTorch (`.pt`, `.pth`), and ONNX (`.onnx`).

**Q: What dataset format is required?**
A: CSV files only. The first row must be column headers. Max 100 MB.

**Q: Can I customise template thresholds?**
A: Yes. When applying a template, click "Customize & Apply" to adjust any threshold or add/remove rules.

**Q: What happens if a validation fails?**
A: The result shows FAIL with details. Use the Root-Cause Analysis feature to understand why and get recommendations.

**Q: How do I export results for regulators?**
A: From any validation result, click "Download PDF Report" or "Export as JSON". From the project traceability page, click "Export as CSV".

**Q: Is my data stored securely?**
A: Models and datasets are stored on the server filesystem. All actions are logged in the audit trail. JWT authentication protects all API endpoints.

---

## 6. Legal & Regulatory Context

This platform helps comply with:

- **EU AI Act** — Risk-based regulation requiring transparency and fairness for high-risk AI.
- **GDPR Article 22** — Right not to be subject to decisions based solely on automated processing.
- **US Equal Credit Opportunity Act (ECOA)** — Prohibits discrimination in lending (80 % rule).
- **EEOC Uniform Guidelines** — Four-fifths rule for employment selection.
- **HIPAA** — Privacy safeguards for healthcare data.

> **Disclaimer:** This platform provides *tools* for ethical AI assessment. It does not constitute legal advice. Consult with legal counsel for compliance decisions.
