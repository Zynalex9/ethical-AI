# Ethical AI Validation — Knowledge Base

> A comprehensive guide to every concept, metric, and technique used by the Ethical AI Governance Platform.

---

## Table of Contents

1. [Fairness](#1-fairness)
2. [Privacy](#2-privacy)
3. [Transparency & Explainability](#3-transparency--explainability)
4. [Accountability](#4-accountability)
5. [Traceability](#5-traceability)
6. [Remediation](#6-remediation)
7. [Glossary](#7-glossary)

---

## 1. Fairness

Fairness in machine learning means that a model's predictions do **not systematically advantage or disadvantage** people based on sensitive attributes such as race, gender, age, or disability.

### 1.1 Why Fairness Matters

Deployed AI systems influence hiring, lending, criminal justice, healthcare, and more. An unfair model can perpetuate or amplify existing societal biases, leading to discrimination at scale. Regulatory frameworks (EU AI Act, US EO 13960) increasingly mandate fairness audits.

### 1.2 Protected / Sensitive Attributes

A **sensitive attribute** (also called a *protected attribute*) is a characteristic that should not influence the model's decision. Common examples:

| Attribute | Examples |
|-----------|----------|
| Race / Ethnicity | White, Black, Asian, Hispanic |
| Gender | Male, Female, Non-binary |
| Age | Age groups or continuous |
| Disability | Yes / No |
| Religion | Various |

### 1.3 Fairness Metrics

#### Demographic Parity (Statistical Parity)

**Definition:** The probability of a positive prediction should be the same across all groups.

$$P(\hat{Y} = 1 \mid A = a) = P(\hat{Y} = 1 \mid A = b) \quad \forall\; a, b$$

- **Demographic Parity Ratio** = $\frac{\min(\text{selection rates})}{\max(\text{selection rates})}$
- A ratio of **1.0** = perfect parity; below **0.8** is generally considered disparate impact.

#### Equalized Odds

**Definition:** The model should have equal True Positive Rate (TPR) *and* equal False Positive Rate (FPR) across groups.

$$P(\hat{Y}=1 \mid Y=y, A=a) = P(\hat{Y}=1 \mid Y=y, A=b) \quad \forall\; y \in \{0,1\}$$

This ensures the model is equally accurate for each group, regardless of whether the true label is positive or negative.

#### Equal Opportunity

A relaxation of equalized odds that requires only **equal TPR** across groups (ignoring FPR):

$$P(\hat{Y}=1 \mid Y=1, A=a) = P(\hat{Y}=1 \mid Y=1, A=b)$$

#### Disparate Impact & Four-Fifths Rule

The **Four-Fifths (80%) Rule** (from US EEOC Uniform Guidelines) states that the selection rate for any protected group must be at least 80% of the group with the highest rate:

$$\frac{\text{Selection Rate}_{\text{minority}}}{\text{Selection Rate}_{\text{majority}}} \geq 0.8$$

If this ratio is below 0.8, there is **adverse / disparate impact**.

#### Predictive Parity

The **Positive Predictive Value** (precision) should be the same across groups:

$$P(Y=1 \mid \hat{Y}=1, A=a) = P(Y=1 \mid \hat{Y}=1, A=b)$$

### 1.4 Confusion Matrix by Group

For each demographic group, the system computes:

|  | Predicted Positive | Predicted Negative |
|--|-------------------|--------------------|
| **Actually Positive** | True Positive (TP) | False Negative (FN) |
| **Actually Negative** | False Positive (FP) | True Negative (TN) |

Comparing these across groups reveals where a model treats groups differently.

### 1.5 Bias Mitigation Strategies

| Stage | Technique | Description |
|-------|-----------|-------------|
| Pre-processing | Reweighing | Assign sample weights to balance group outcomes |
| Pre-processing | Disparate Impact Remover | Transform features to remove correlation with sensitive attribute |
| In-processing | Adversarial Debiasing | Add adversary network penalising group-predictive representations |
| Post-processing | Threshold Adjustment | Use different classification thresholds per group |
| Post-processing | Reject Option Classification | Flip uncertain predictions near the decision boundary |

---

## 2. Privacy

Privacy validation ensures that data and models **do not expose personally identifiable information (PII)** or allow reconstruction of individual records.

### 2.1 PII Detection

**Personally Identifiable Information (PII)** refers to any data that can identify a specific individual:

- **Direct identifiers:** Name, SSN, email, phone number, medical record number
- **Quasi-identifiers:** ZIP code, date of birth, gender — these *combined* can re-identify individuals (see k-Anonymity below)

The platform scans dataset columns for PII using pattern matching (regex for emails, SSNs, phone numbers) and column-name heuristics (e.g., columns named `name`, `ssn`, `email`).

### 2.2 k-Anonymity

**Definition:** A dataset satisfies **k-anonymity** if every combination of quasi-identifier values appears in at least *k* rows.

**Intuition:** No individual can be distinguished from at least $k-1$ other individuals sharing the same quasi-identifier values.

**Example (k=2):**

| ZIP   | Age | Gender | Disease  |
|-------|-----|--------|----------|
| 10001 | 30  | M      | Flu      |
| 10001 | 30  | M      | Cold     |
| 10002 | 45  | F      | Diabetes |
| 10002 | 45  | F      | Asthma   |

Each quasi-identifier group (ZIP + Age + Gender) has at least 2 rows → **k=2 satisfied**.

**Limitations:** k-Anonymity does not protect against **attribute disclosure** — if all records in a group share the same sensitive value, the attacker still learns the sensitive value.

### 2.3 l-Diversity

**Definition:** A dataset satisfies **l-diversity** if, within each quasi-identifier equivalence class, there are at least *l* "well-represented" distinct values of the sensitive attribute.

**Intuition:** Prevents attribute disclosure by ensuring diversity in the sensitive column within each group.

**Example (l=2):**

| ZIP   | Age | Disease  |
|-------|-----|----------|
| 10001 | 30  | Flu      |
| 10001 | 30  | Diabetes |
| 10002 | 45  | Cold     |
| 10002 | 45  | Cold     | ← **Fails l=2** (only 1 distinct disease)

### 2.4 Quasi-Identifiers

**Quasi-identifiers** are attributes that are not unique identifiers by themselves but can be **combined** to re-identify individuals. Research (Sweeney, 2000) showed that 87% of the US population can be uniquely identified using just **ZIP code + date of birth + gender**.

Common quasi-identifiers:
- ZIP / postal code
- Date of birth / age
- Gender
- Occupation
- Marital status

### 2.5 Differential Privacy (DP)

**Definition:** A randomised algorithm $\mathcal{M}$ satisfies **$(\varepsilon, \delta)$-differential privacy** if for all datasets $D_1, D_2$ differing in at most one record, and for all subsets $S$ of outputs:

$$P(\mathcal{M}(D_1) \in S) \leq e^{\varepsilon} \cdot P(\mathcal{M}(D_2) \in S) + \delta$$

**Intuition:** Adding or removing any single individual's data barely changes the output, so an individual's participation cannot be inferred.

#### Key Parameters

| Parameter | Meaning |
|-----------|---------|
| **ε (epsilon)** | Privacy budget. Lower ε = stronger privacy. Typical values: 0.1 (strong) to 10 (weak). |
| **δ (delta)** | Probability of privacy breach. Should be ≪ 1/n (dataset size). |

#### Mechanism

The platform uses the **Laplace mechanism**: calibrated noise drawn from a Laplace distribution is added to the true query result. Noise scale = $\frac{\Delta f}{\varepsilon}$ where $\Delta f$ is the **sensitivity** (maximum change from adding/removing one record).

#### What the Platform Checks

1. **Noise Injection:** Adds Laplace noise to statistical queries on the dataset.
2. **Membership Inference Test:** Trains an attack model to determine whether specific records were in the training set. Lower attack accuracy = better privacy.
3. **Epsilon Reporting:** Reports the effective ε used and whether it meets the user's target.

### 2.6 HIPAA Safe Harbor De-identification

**HIPAA** (Health Insurance Portability and Accountability Act) is a US federal law that protects health information. The **Safe Harbor method** requires removing or generalising **18 specific identifiers**:

| # | Identifier | Description |
|---|-----------|-------------|
| 1 | Names | Full name, last, first, initials |
| 2 | Geographic data | Addresses, ZIP codes (first 3 digits if population < 20k) |
| 3 | Dates | All dates except year (birth, admission, discharge, death) |
| 4 | Telephone numbers | All phone numbers |
| 5 | Fax numbers | All fax numbers |
| 6 | Email addresses | All email addresses |
| 7 | Social Security Numbers | SSN |
| 8 | Medical Record Numbers | MRN |
| 9 | Health Plan Beneficiary Numbers | Insurance IDs |
| 10 | Account Numbers | Financial account numbers |
| 11 | Certificate/License Numbers | Professional licenses |
| 12 | Vehicle Identifiers | VIN, licence plates |
| 13 | Device Identifiers | Serial numbers of medical devices |
| 14 | Web URLs | Personal web addresses |
| 15 | IP Addresses | Network addresses |
| 16 | Biometric Identifiers | Fingerprints, voiceprints |
| 17 | Full-face Photos | Photographs and comparable images |
| 18 | Any other Unique Identifier | Any code that could identify an individual |

The platform scans your dataset's columns against these 18 categories and reports which are **found**, **not found**, or **at risk**.

---

## 3. Transparency & Explainability

Transparency ensures stakeholders can **understand, inspect, and question** how a model makes decisions.

### 3.1 SHAP (SHapley Additive exPlanations)

**Origin:** Based on Shapley values from cooperative game theory (Lloyd Shapley, 1953; Lundberg & Lee, 2017).

**Intuition:** Each feature is a "player" in a game. The Shapley value is the average marginal contribution of a feature across all possible coalitions of features.

$$\phi_i = \sum_{S \subseteq N \setminus \{i\}} \frac{|S|!\;(|N|-|S|-1)!}{|N|!} \left[ f(S \cup \{i\}) - f(S) \right]$$

Where:
- $N$ = set of all features
- $S$ = a subset of features (a "coalition")
- $f(S)$ = model prediction using features in $S$
- $\phi_i$ = Shapley value (SHAP value) of feature $i$

#### What the Platform Shows

| Visualisation | Description |
|---------------|-------------|
| **Global Feature Importance** | Mean absolute SHAP values across all samples — shows which features matter most *overall*. |
| **Local SHAP Explanation** | SHAP values for a single prediction — shows how each feature pushed the prediction higher or lower for that instance. |

#### Interpreting SHAP Values

- **Positive SHAP** → feature pushed the prediction **higher** (toward positive class)
- **Negative SHAP** → feature pushed the prediction **lower** (toward negative class)
- **Zero SHAP** → feature had no influence on this prediction

### 3.2 LIME (Local Interpretable Model-agnostic Explanations)

**Origin:** Ribeiro, Singh, & Guestrin (2016).

**How it works:**
1. For a given instance $x$, generate **perturbed samples** by randomly varying features near $x$.
2. Get the black-box model's predictions for all perturbed samples.
3. Fit a **simple, interpretable model** (e.g., linear regression) on the perturbed data, weighted by proximity to $x$.
4. The coefficients of this simple model are the **feature contributions**.

$$\text{explanation}(x) = \arg\min_{g \in G}\; \mathcal{L}(f, g, \pi_x) + \Omega(g)$$

Where:
- $f$ = the original model
- $g$ = the interpretable surrogate model
- $\pi_x$ = proximity measure (weights nearby samples more)
- $\Omega(g)$ = complexity penalty (keeps $g$ simple)

#### Explanation Fidelity

**Fidelity** measures how well the LIME surrogate model $g$ approximates the original model $f$ in the local neighbourhood:

$$\text{Fidelity} = 1 - \text{mean}(|f(x) - g(x)|)$$

- **Fidelity ≥ 0.8** → LIME faithfully represents the model locally (good)
- **Fidelity < 0.5** → LIME is a poor local approximation (interpret with caution)

#### Why Contributions May Be ≈ 0

If all LIME feature contributions are near zero, it typically means:
- The model's prediction barely changes regardless of feature perturbations (e.g., the model is always predicting the same class).
- The dataset lacks sufficient variance in the features used.
- The model is very simple (e.g., predicts a constant).

### 3.3 Feature Importance

Feature importance ranks input features by their influence on the model. Methods include:

| Method | How It Works |
|--------|-------------|
| **Permutation Importance** | Randomly shuffle one feature at a time and measure accuracy drop |
| **SHAP Importance** | Mean |SHAP value| across predictions |
| **Gini / MDI** | For tree models: total decrease in node impurity from splitting on a feature |
| **Coefficients** | For linear models: absolute weight magnitudes |

### 3.4 Model Card

A **Model Card** (Mitchell et al., 2019) is a documentation artefact describing:
- Model type and version
- Training data characteristics
- Performance metrics (accuracy, precision, recall, F1)
- Intended use and limitations
- Ethical considerations

---

## 4. Accountability

Accountability ensures that every action — model training, data processing, validation runs — is **logged, auditable, and attributable** to a user.

### 4.1 Audit Trail

Every validation run is recorded with:
- **Who** triggered it (user ID)
- **When** it ran (timestamps)
- **What** was validated (model, dataset, configuration)
- **Results** obtained (pass/fail, metric values)

### 4.2 MLflow Integration

[MLflow](https://mlflow.org/) is an open-source platform for managing the ML lifecycle. The platform uses MLflow to:

- **Track experiments:** Every validation run is logged as an MLflow run with parameters, metrics, and artefacts.
- **Store artefacts:** SHAP plots, LIME explanations, fairness reports are saved as ML artefacts.
- **Version models:** Model versions are tracked for reproducibility.
- **Compare runs:** Users can compare validation results across time.

### 4.3 Celery Task Tracking

Long-running validations execute as **asynchronous Celery tasks** so the UI remains responsive. Task state (PENDING → PROGRESS → SUCCESS / FAILURE) is tracked in real-time via Redis.

---

## 5. Traceability

Traceability provides an **end-to-end chain** from ethical requirements to datasets, models, and validation outcomes.

### 5.1 Requirement Traceability Matrix (RTM)

The RTM maps:

```
Requirement → Dataset → Model → Validation Result → Pass/Fail
```

This ensures:
- Every ethical requirement has been validated
- Every validation can be traced back to a specific requirement
- Gaps (unvalidated requirements) are visible

### 5.2 Compliance History

For each requirement, the platform records all past validation runs and their outcomes, enabling:
- **Trend analysis:** Is compliance improving or degrading?
- **Regression detection:** Was a passing requirement broken by a new model/dataset?

### 5.3 Root-Cause Analysis

When a validation fails, the platform performs automated root-cause analysis:
1. Identifies which metrics failed and by how much (the "gap")
2. Links the failure to the violated requirement
3. Analyses the model's behaviour pattern
4. Generates actionable recommendations

---

## 6. Remediation

When validations fail, the Remediation workflow guides users through fixing issues step by step.

### 6.1 Guided Remediation Workflow

For each ethical principle (Fairness, Privacy, Transparency), the platform generates a checklist of remediation steps. Each step can be:

- **Pending** — Not yet started
- **In Progress** — Currently being worked on
- **Completed** — Verified as resolved
- **Skipped** — Intentionally not applicable

### 6.2 Common Remediation Actions

| Principle | Common Remediation Steps |
|-----------|------------------------|
| **Fairness** | Rebalance training data, apply reweighting, adjust thresholds, remove biased features |
| **Privacy** | Remove PII columns, generalise quasi-identifiers, apply differential privacy, ensure k-anonymity |
| **Transparency** | Add feature documentation, generate model card, improve explanation fidelity, simplify model |

---

## 7. Glossary

| Term | Definition |
|------|-----------|
| **Adverse / Disparate Impact** | When a selection process disproportionately affects a protected group |
| **Confusion Matrix** | Table of TP, FP, TN, FN counts for a classifier |
| **Demographic Parity** | All groups receive positive predictions at the same rate |
| **Differential Privacy (DP)** | Mathematical guarantee bounding what an observer can learn about any individual |
| **Epsilon (ε)** | Privacy budget in differential privacy — lower = more private |
| **Equal Opportunity** | Equal true positive rates across groups |
| **Equalized Odds** | Equal TPR and FPR across groups |
| **Explanation Fidelity** | How well LIME's surrogate model approximates the real model locally |
| **Feature Importance** | Ranking of features by their influence on model predictions |
| **Four-Fifths Rule** | Adverse impact exists if selection rate < 80% of the highest group |
| **HIPAA** | US law protecting health information; Safe Harbor requires removing 18 identifiers |
| **k-Anonymity** | Each quasi-identifier combination appears in ≥ k rows |
| **l-Diversity** | Each equivalence class has ≥ l distinct sensitive attribute values |
| **Laplace Mechanism** | DP technique adding Laplace-distributed noise proportional to query sensitivity |
| **LIME** | Local Interpretable Model-agnostic Explanations — fits a simple surrogate model locally |
| **Membership Inference** | Privacy attack testing whether a record was in the training set |
| **MLflow** | Open-source platform for ML experiment tracking, model management, and deployment |
| **Model Card** | Standardised documentation of a model's capabilities, limitations, and ethical considerations |
| **PII** | Personally Identifiable Information — data that can identify a specific person |
| **Predictive Parity** | Equal precision (PPV) across groups |
| **Quasi-Identifier** | Attributes that can re-identify individuals when combined (ZIP, DOB, gender) |
| **RTM** | Requirement Traceability Matrix — links requirements to validation results |
| **Selection Rate** | Proportion of a group receiving a positive prediction |
| **Sensitive Attribute** | A protected demographic feature (race, gender, age, etc.) |
| **SHAP** | SHapley Additive exPlanations — game-theoretic feature attribution method |
| **Shapley Value** | The average marginal contribution of a feature across all possible feature coalitions |

---

*This knowledge base is auto-generated for the Ethical AI Governance Platform. For academic references, see the original papers cited in each section.*
