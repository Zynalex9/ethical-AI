# Benchmark Datasets for Ethical AI Validation

This directory contains three widely-used benchmark datasets for testing fairness and bias in AI systems.

## 1. COMPAS Recidivism Dataset (`compas.csv`)

**Source:** ProPublica COMPAS Analysis  
**URL:** https://github.com/propublica/compas-analysis

**Description:**  
Criminal recidivism risk assessment dataset from Broward County, Florida. Used to study racial bias in algorithmic risk assessment tools used by the criminal justice system.

**Size:** ~7,000 rows, 53 columns

**Key Columns:**
- **Target Column:** `two_year_recid` (1 = did recidivate within 2 years, 0 = did not)
- **Sensitive Attributes:** 
  - `race` (African-American, Caucasian, Hispanic, Asian, Native American, Other)
  - `sex` (Male, Female)
  - `age_cat` (Less than 25, 25-45, Greater than 45)
- **Important Features:**
  - `age`: Age in years
  - `priors_count`: Number of prior convictions
  - `c_charge_degree`: Degree of current charge (F=Felony, M=Misdemeanor)
  - `decile_score`: COMPAS risk score (1-10, higher = higher risk)

**Ethical Issues:**
- Documented racial bias: Black defendants were more likely to be incorrectly flagged as high risk
- Used in ProPublica's "Machine Bias" investigation (2016)

**Fairness Metrics to Test:**
- Demographic Parity across race
- Equal Opportunity (TPR) across race
- Equalized Odds across race

---

## 2. Adult Income Dataset (`adult_income.csv`)

**Source:** UCI Machine Learning Repository  
**URL:** https://archive.ics.uci.edu/ml/datasets/adult

**Description:**  
Census data from 1994 used to predict whether a person's income exceeds $50K/year. Widely used for fairness research due to sensitive demographic attributes.

**Size:** ~48,000 rows, 15 columns

**Key Columns:**
- **Target Column:** `income` (">50K" or "<=50K")
- **Sensitive Attributes:**
  - `sex` (Male, Female)
  - `race` (White, Black, Asian-Pac-Islander, Amer-Indian-Eskimo, Other)
  - `native-country`
- **Important Features:**
  - `age`: Age in years
  - `education`: Highest education level
  - `occupation`: Job type
  - `hours-per-week`: Work hours per week
  - `marital-status`: Marital status
  - `relationship`: Relationship status

**Ethical Issues:**
- Gender and race disparities in income prediction
- Potential for reinforcing historical discrimination
- Proxy variables (e.g., occupation correlates with gender)

**Fairness Metrics to Test:**
- Demographic Parity across sex and race
- Equal Opportunity across sex and race
- Disparate Impact Ratio

---

## 3. German Credit Dataset (`german_credit.csv`)

**Source:** UCI Machine Learning Repository  
**URL:** https://archive.ics.uci.edu/ml/datasets/statlog+(german+credit+data)

**Description:**  
Credit risk assessment dataset from a German bank. Used to study fairness in lending and credit scoring algorithms, relevant to ECOA (Equal Credit Opportunity Act) compliance.

**Size:** 1,000 rows, 21 columns

**Key Columns:**
- **Target Column:** `credit_risk` (1 = good credit, 2 = bad credit)
- **Sensitive Attributes:**
  - `sex` (Derived from personal_status: male, female)
  - `age`: Age in years (can be binned for fairness analysis)
  - `foreign_worker` (yes, no)
- **Important Features:**
  - `duration`: Credit duration in months
  - `credit_amount`: Credit amount in DM
  - `installment_rate`: Installment rate as % of disposable income
  - `present_residence`: Present residence since (years)
  - `property`: Property ownership
  - `existing_credits`: Number of existing credits
  - `job`: Job type/skill level

**Ethical Issues:**
- Gender and age bias in credit approval
- Relevant to financial fairness and ECOA compliance
- Small dataset size makes fairness harder to achieve

**Fairness Metrics to Test:**
- Demographic Parity across sex and age groups
- Equal Opportunity for loan approval
- Disparate Impact (80% rule for lending)

---

## Data Processing Notes

### Preprocessing Required:
1. **COMPAS:** 
   - Filter to only relevant columns
   - Convert categorical columns to numeric if needed
   - Handle missing values in `days_b_screening_arrest`

2. **Adult Income:**
   - Remove rows with missing values (marked as "?")
   - Encode categorical variables
   - Normalize continuous features if needed

3. **German Credit:**
   - Decode numeric categorical features (many are encoded as numbers)
   - Create derived `sex` column from `personal_status`
   - Recode target: 1=good (positive class), 2=bad (negative class)

### Validation Recommendations:

**For COMPAS:**
- Test fairness across `race` (primary sensitive attribute)
- Threshold: Demographic parity ratio >= 0.8 (FairML standard)
- Check for proxy variables: zip code, neighborhood

**For Adult Income:**
- Test fairness across `sex` and `race`
- Threshold: Demographic parity difference <= 0.1
- Check for intersectionality (e.g., Black females)

**For German Credit:**
- Test fairness across `sex` and `age`
- Threshold: Disparate Impact >= 0.8 (ECOA 80% rule)
- Privacy: Check for PII in credit history fields

---

## Citations

**COMPAS:**
```
Angwin, J., Larson, J., Mattu, S., & Kirchner, L. (2016). 
Machine Bias. ProPublica. 
https://www.propublica.org/article/machine-bias-risk-assessments-in-criminal-sentencing
```

**Adult Income:**
```
Dua, D. and Graff, C. (2019). UCI Machine Learning Repository. 
University of California, Irvine, School of Information and Computer Sciences.
http://archive.ics.uci.edu/ml
```

**German Credit:**
```
Hofmann, H. (1994). Statlog (German Credit Data) Data Set. 
UCI Machine Learning Repository.
https://archive.ics.uci.edu/ml/datasets/statlog+(german+credit+data)
```

---

## Usage in Platform

These datasets are automatically loaded into projects via the "Load Benchmark Dataset" feature. The system:

1. Detects sensitive attributes automatically
2. Sets the target column
3. Profiles the data (distributions, missing values)
4. Suggests appropriate fairness requirements based on dataset characteristics

**Example Use Cases:**
- **COMPAS:** Criminal justice fairness validation
- **Adult Income:** Employment/income fairness validation  
- **German Credit:** Financial lending fairness validation (ECOA compliance)
