/**
 * KnowledgeBasePage – in-app reference for all ethical AI concepts.
 *
 * Accordion sections covering Fairness, Privacy, Transparency, Accountability,
 * Traceability, and a full glossary.
 */

import { useState } from 'react';
import {
    Box,
    Container,
    Typography,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Chip,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Divider,
    Alert,
    TextField,
    InputAdornment,
} from '@mui/material';
import {
    ExpandMore as ExpandIcon,
    Balance as FairnessIcon,
    Security as PrivacyIcon,
    Visibility as TransparencyIcon,
    Gavel as AccountabilityIcon,
    AccountTree as TraceIcon,
    MenuBook as BookIcon,
    Search as SearchIcon,
} from '@mui/icons-material';

/* ---------- Section data ---------- */

interface GlossaryEntry {
    term: string;
    definition: string;
}

const glossary: GlossaryEntry[] = [
    { term: 'Adverse / Disparate Impact', definition: 'When a selection process disproportionately affects a protected group.' },
    { term: 'Confusion Matrix', definition: 'Table of True Positives, False Positives, True Negatives, False Negatives for a classifier.' },
    { term: 'Demographic Parity', definition: 'All demographic groups receive positive predictions at the same rate.' },
    { term: 'Differential Privacy (DP)', definition: 'Mathematical guarantee bounding what an observer can learn about any individual from the output of an algorithm. Controlled by epsilon (ε).' },
    { term: 'Epsilon (ε)', definition: 'Privacy budget in differential privacy. Lower ε = stronger privacy guarantee. Typical range: 0.1 (strong) – 10 (weak).' },
    { term: 'Equal Opportunity', definition: 'Requires equal True Positive Rates (TPR) across all demographic groups.' },
    { term: 'Equalized Odds', definition: 'Requires both equal TPR and equal FPR across all groups.' },
    { term: 'Explanation Fidelity', definition: 'How faithfully the LIME surrogate model approximates the original model locally. Fidelity = 1 − mean(|f(x) − g(x)|).' },
    { term: 'Feature Importance', definition: 'Ranking of input features by their influence on model predictions (can be computed via SHAP, permutation, or Gini impurity).' },
    { term: 'Four-Fifths (80%) Rule', definition: 'Adverse impact exists if any group\'s selection rate is less than 80% of the highest group\'s rate (US EEOC guidelines).' },
    { term: 'HIPAA Safe Harbor', definition: 'HIPAA de-identification method requiring removal of 18 specific identifiers from health data.' },
    { term: 'k-Anonymity', definition: 'A dataset satisfies k-anonymity if every combination of quasi-identifier values appears in at least k rows.' },
    { term: 'l-Diversity', definition: 'Within each quasi-identifier equivalence class, there must be at least l distinct values of the sensitive attribute.' },
    { term: 'Laplace Mechanism', definition: 'Differential privacy technique that adds Laplace-distributed noise proportional to the query sensitivity divided by epsilon.' },
    { term: 'LIME', definition: 'Local Interpretable Model-agnostic Explanations — generates a simple surrogate model around a specific prediction to explain it.' },
    { term: 'Membership Inference', definition: 'Privacy attack that tries to determine whether a specific record was part of the training dataset.' },
    { term: 'MLflow', definition: 'Open-source platform for ML experiment tracking, model management, and deployment. Used for our audit trail.' },
    { term: 'Model Card', definition: 'Standardised documentation of a model\'s capabilities, performance metrics, limitations, and ethical considerations.' },
    { term: 'PII', definition: 'Personally Identifiable Information — any data that can identify a specific person (name, SSN, email, phone, etc.).' },
    { term: 'Predictive Parity', definition: 'Equal precision (Positive Predictive Value) across demographic groups.' },
    { term: 'Quasi-Identifier', definition: 'Attributes that individually are not unique but can re-identify individuals when combined (e.g., ZIP + date of birth + gender).' },
    { term: 'RTM', definition: 'Requirement Traceability Matrix — maps ethical requirements to datasets, models, and validation results.' },
    { term: 'Selection Rate', definition: 'Proportion of a group that receives a positive prediction from the model.' },
    { term: 'Sensitive Attribute', definition: 'A protected demographic feature (race, gender, age) that should not influence model predictions unfairly.' },
    { term: 'SHAP', definition: 'SHapley Additive exPlanations — game-theoretic method assigning each feature a contribution value based on Shapley values.' },
    { term: 'Shapley Value', definition: 'From cooperative game theory — the average marginal contribution of a feature across all possible coalitions of features.' },
];

/* ---------- Styled section ---------- */

interface SectionProps {
    icon: React.ReactNode;
    color: string;
    title: string;
    children: React.ReactNode;
    defaultExpanded?: boolean;
}

function Section({ icon, color, title, children, defaultExpanded }: SectionProps) {
    return (
        <Accordion defaultExpanded={defaultExpanded} sx={{ '&:before': { display: 'none' }, mb: 1.5 }}>
            <AccordionSummary expandIcon={<ExpandIcon />} sx={{ '& .MuiAccordionSummary-content': { alignItems: 'center', gap: 1 } }}>
                <Box sx={{ color, display: 'flex', alignItems: 'center' }}>{icon}</Box>
                <Typography variant="h6" fontWeight={700}>{title}</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0 }}>{children}</AccordionDetails>
        </Accordion>
    );
}

function P({ children }: { children: React.ReactNode }) {
    return <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7 }}>{children}</Typography>;
}

function H3({ children }: { children: React.ReactNode }) {
    return <Typography variant="subtitle1" fontWeight={700} sx={{ mt: 2, mb: 1 }}>{children}</Typography>;
}

/* ---------- Page ---------- */

export default function KnowledgeBasePage() {
    const [search, setSearch] = useState('');

    const filteredGlossary = glossary.filter(
        (g) =>
            g.term.toLowerCase().includes(search.toLowerCase()) ||
            g.definition.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
                <BookIcon color="primary" sx={{ fontSize: 36 }} />
                <Typography variant="h4" fontWeight={700}>Knowledge Base</Typography>
            </Box>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                Learn about every fairness metric, privacy technique, explainability method, and accountability mechanism used by the platform.
            </Typography>

            {/* ── 1. FAIRNESS ────────────────────────────────── */}
            <Section icon={<FairnessIcon />} color="#4caf50" title="Fairness" defaultExpanded>
                <P>
                    Fairness in machine learning means that a model's predictions do <strong>not systematically advantage
                    or disadvantage</strong> people based on sensitive attributes such as race, gender, age, or disability.
                </P>

                <H3>Protected / Sensitive Attributes</H3>
                <P>
                    A <strong>sensitive attribute</strong> is a characteristic that should not influence the model's decision.
                    Examples include race, gender, age, disability, and religion. Regulatory frameworks (EU AI Act, US EO 13960)
                    increasingly mandate fairness audits.
                </P>

                <H3>Demographic Parity (Statistical Parity)</H3>
                <P>
                    The probability of a positive prediction should be the <strong>same across all groups</strong>.
                    The <strong>Demographic Parity Ratio</strong> = min(selection rates) / max(selection rates).
                    A ratio of 1.0 = perfect parity; below 0.8 is generally considered disparate impact.
                </P>

                <H3>Equalized Odds</H3>
                <P>
                    The model should have <strong>equal True Positive Rate (TPR)</strong> and <strong>equal False Positive Rate (FPR)
                    </strong> across all groups. This ensures the model is equally accurate for each group regardless of the true label.
                </P>

                <H3>Equal Opportunity</H3>
                <P>
                    A relaxation of equalized odds requiring only <strong>equal TPR</strong> across groups (ignoring FPR).
                    In other words, equally qualified individuals from each group have the same chance of being correctly identified.
                </P>

                <H3>Four-Fifths (80%) Rule</H3>
                <Alert severity="warning" variant="outlined" sx={{ mb: 1.5 }}>
                    From the US EEOC Uniform Guidelines: if any group's selection rate is less than 80% of the highest group's rate,
                    there is <strong>adverse / disparate impact</strong>.
                </Alert>

                <H3>Predictive Parity</H3>
                <P>
                    The Positive Predictive Value (precision) should be the same across groups — when the model says "positive",
                    it should be equally reliable for every group.
                </P>

                <H3>Confusion Matrix by Group</H3>
                <P>
                    For each demographic group the platform computes True Positives (TP), False Positives (FP),
                    True Negatives (TN), and False Negatives (FN). Comparing these across groups reveals where
                    a model treats groups differently.
                </P>

                <H3>Bias Mitigation Strategies</H3>
                <TableContainer component={Paper} variant="outlined" sx={{ mb: 1 }}>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell><strong>Stage</strong></TableCell>
                                <TableCell><strong>Technique</strong></TableCell>
                                <TableCell><strong>Description</strong></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            <TableRow><TableCell>Pre-processing</TableCell><TableCell>Reweighing</TableCell><TableCell>Assign sample weights to balance group outcomes</TableCell></TableRow>
                            <TableRow><TableCell>Pre-processing</TableCell><TableCell>Disparate Impact Remover</TableCell><TableCell>Transform features to remove correlation with sensitive attribute</TableCell></TableRow>
                            <TableRow><TableCell>In-processing</TableCell><TableCell>Adversarial Debiasing</TableCell><TableCell>Add adversary network penalising group-predictive representations</TableCell></TableRow>
                            <TableRow><TableCell>Post-processing</TableCell><TableCell>Threshold Adjustment</TableCell><TableCell>Use different classification thresholds per group to equalise outcomes</TableCell></TableRow>
                            <TableRow><TableCell>Post-processing</TableCell><TableCell>Reject Option</TableCell><TableCell>Flip uncertain predictions near the decision boundary</TableCell></TableRow>
                        </TableBody>
                    </Table>
                </TableContainer>
            </Section>

            {/* ── 2. PRIVACY ─────────────────────────────────── */}
            <Section icon={<PrivacyIcon />} color="#ff9800" title="Privacy">
                <P>
                    Privacy validation ensures that data and models <strong>do not expose personally identifiable information (PII)</strong> or
                    allow reconstruction of individual records.
                </P>

                <H3>PII Detection</H3>
                <P>
                    <strong>Personally Identifiable Information (PII)</strong> is any data that can identify a specific individual —
                    names, SSNs, emails, phone numbers, medical record numbers.
                    The platform scans dataset columns using pattern matching and column-name heuristics.
                </P>

                <H3>k-Anonymity</H3>
                <P>
                    A dataset satisfies <strong>k-anonymity</strong> if every combination of quasi-identifier values
                    appears in at least <em>k</em> rows. No individual can be distinguished from at least k−1 others
                    sharing the same quasi-identifier values.
                </P>
                <Alert severity="info" variant="outlined" sx={{ mb: 1.5 }}>
                    <strong>Limitation:</strong> k-Anonymity does not protect against <em>attribute disclosure</em> — if all records
                    in a group share the same sensitive value, the attacker still learns it. Use l-diversity to address this.
                </Alert>

                <H3>l-Diversity</H3>
                <P>
                    Within each quasi-identifier equivalence class, there must be at least <em>l</em> distinct values
                    of the sensitive attribute. This prevents attribute disclosure by ensuring diversity in the sensitive column.
                </P>

                <H3>Quasi-Identifiers</H3>
                <P>
                    <strong>Quasi-identifiers</strong> are attributes that are not unique by themselves but can be combined
                    to re-identify individuals. Research (Sweeney, 2000) showed that 87% of the US population can be
                    uniquely identified using just <strong>ZIP code + date of birth + gender</strong>.
                </P>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1.5 }}>
                    {['ZIP / Postal Code', 'Date of Birth', 'Gender', 'Age', 'Occupation', 'Marital Status'].map((q) => (
                        <Chip key={q} label={q} size="small" variant="outlined" />
                    ))}
                </Box>

                <H3>Differential Privacy (DP)</H3>
                <P>
                    A randomised algorithm satisfies <strong>(ε, δ)-differential privacy</strong> if adding or removing
                    any single individual's data barely changes the output. The key parameter is <strong>epsilon (ε)</strong>:
                    lower ε = stronger privacy.
                </P>
                <TableContainer component={Paper} variant="outlined" sx={{ mb: 1.5 }}>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell><strong>Parameter</strong></TableCell>
                                <TableCell><strong>Meaning</strong></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            <TableRow><TableCell>ε (epsilon)</TableCell><TableCell>Privacy budget. Lower = stronger privacy. Typical: 0.1 (strong) – 10 (weak).</TableCell></TableRow>
                            <TableRow><TableCell>δ (delta)</TableCell><TableCell>Probability of privacy breach. Should be much smaller than 1/n.</TableCell></TableRow>
                            <TableRow><TableCell>Laplace Mechanism</TableCell><TableCell>Adds calibrated Laplace noise with scale = sensitivity / ε.</TableCell></TableRow>
                        </TableBody>
                    </Table>
                </TableContainer>
                <P>
                    The platform performs: (1) noise injection via Laplace mechanism, (2) membership inference attack
                    testing, and (3) effective ε reporting.
                </P>

                <H3>HIPAA Safe Harbor De-identification</H3>
                <P>
                    <strong>HIPAA</strong> (Health Insurance Portability and Accountability Act) protects health information.
                    The <strong>Safe Harbor method</strong> requires removing or generalising <strong>18 specific identifiers</strong> from the data:
                </P>
                <TableContainer component={Paper} variant="outlined" sx={{ mb: 1 }}>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell><strong>#</strong></TableCell>
                                <TableCell><strong>Identifier</strong></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {[
                                'Names', 'Geographic data (addresses, ZIP)', 'Dates (except year)',
                                'Telephone numbers', 'Fax numbers', 'Email addresses',
                                'Social Security Numbers', 'Medical Record Numbers',
                                'Health Plan Beneficiary Numbers', 'Account Numbers',
                                'Certificate / License Numbers', 'Vehicle Identifiers',
                                'Device Identifiers', 'Web URLs', 'IP Addresses',
                                'Biometric Identifiers', 'Full-face Photos', 'Any other Unique Identifier',
                            ].map((id, i) => (
                                <TableRow key={i}>
                                    <TableCell>{i + 1}</TableCell>
                                    <TableCell>{id}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Section>

            {/* ── 3. TRANSPARENCY ────────────────────────────── */}
            <Section icon={<TransparencyIcon />} color="#2196f3" title="Transparency & Explainability">
                <P>
                    Transparency ensures stakeholders can <strong>understand, inspect, and question</strong> how a model
                    makes decisions.
                </P>

                <H3>SHAP (SHapley Additive exPlanations)</H3>
                <P>
                    Based on Shapley values from cooperative game theory. Each feature is a "player" and the Shapley value
                    is its average marginal contribution across all possible coalitions of features.
                </P>
                <TableContainer component={Paper} variant="outlined" sx={{ mb: 1.5 }}>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell><strong>Visualisation</strong></TableCell>
                                <TableCell><strong>What It Shows</strong></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            <TableRow><TableCell>Global Feature Importance</TableCell><TableCell>Mean |SHAP values| across all samples — which features matter most overall.</TableCell></TableRow>
                            <TableRow><TableCell>Local SHAP Explanation</TableCell><TableCell>SHAP values for a single prediction — how each feature pushed the prediction.</TableCell></TableRow>
                        </TableBody>
                    </Table>
                </TableContainer>
                <Alert severity="success" variant="outlined" sx={{ mb: 1.5 }}>
                    <strong>Interpreting SHAP:</strong> Positive SHAP → pushes prediction higher (toward positive class).
                    Negative SHAP → pushes lower. Zero → no influence.
                </Alert>

                <H3>LIME (Local Interpretable Model-agnostic Explanations)</H3>
                <P>
                    For a given prediction: (1) generate perturbed samples by varying features near the instance,
                    (2) get the black-box model's predictions for all perturbed samples,
                    (3) fit a simple interpretable model (linear regression) weighted by proximity,
                    (4) the coefficients are the feature contributions.
                </P>

                <H3>Explanation Fidelity</H3>
                <P>
                    Measures how well the LIME surrogate approximates the original model locally.
                    <strong> Fidelity = 1 − mean(|f(x) − g(x)|)</strong>. A fidelity ≥ 0.8 is considered good;
                    below 0.5 means interpret LIME with caution.
                </P>

                <H3>Why LIME Contributions May Be ≈ 0</H3>
                <Alert severity="warning" variant="outlined" sx={{ mb: 1.5 }}>
                    If all LIME feature contributions are near zero, it typically means the model's prediction barely
                    changes regardless of feature perturbations (e.g., the model always predicts the same class),
                    or the dataset lacks sufficient variance.
                </Alert>

                <H3>Model Card</H3>
                <P>
                    A <strong>Model Card</strong> (Mitchell et al., 2019) is documentation describing model type,
                    training data, performance metrics, intended use cases, limitations, and ethical considerations.
                </P>
            </Section>

            {/* ── 4. ACCOUNTABILITY ──────────────────────────── */}
            <Section icon={<AccountabilityIcon />} color="#9c27b0" title="Accountability">
                <P>
                    Every action — model training, data processing, validation runs — is <strong>logged, auditable, and attributable</strong> to a user.
                </P>

                <H3>Audit Trail</H3>
                <P>
                    Every validation run records who triggered it, when it ran, what was validated (model, dataset, configuration),
                    and the full results obtained (pass/fail, metric values).
                </P>

                <H3>MLflow Integration</H3>
                <P>
                    The platform uses MLflow to track experiments, store artefacts (SHAP plots, LIME explanations, fairness reports),
                    version models, and compare validation runs across time.
                </P>
            </Section>

            {/* ── 5. TRACEABILITY ────────────────────────────── */}
            <Section icon={<TraceIcon />} color="#00bcd4" title="Traceability">
                <P>
                    Traceability provides an <strong>end-to-end chain</strong> from ethical requirements to datasets,
                    models, and validation outcomes.
                </P>

                <H3>Requirement Traceability Matrix (RTM)</H3>
                <P>
                    The RTM maps: <strong>Requirement → Dataset → Model → Validation Result → Pass/Fail</strong>.
                    This ensures every ethical requirement has been validated, every validation can be traced back to a requirement,
                    and gaps (unvalidated requirements) are immediately visible.
                </P>

                <H3>Compliance History & Regression Detection</H3>
                <P>
                    For each requirement, the platform records all past validation runs and outcomes, enabling trend analysis
                    and automatic regression detection when a previously passing requirement fails with a new model or dataset.
                </P>

                <H3>Root-Cause Analysis</H3>
                <P>
                    When a validation fails, automated root-cause analysis identifies which metrics failed, links the failure
                    to the violated requirement, analyses the model's behaviour pattern, and generates actionable recommendations.
                </P>
            </Section>

            {/* ── 6. GLOSSARY ────────────────────────────────── */}
            <Divider sx={{ my: 3 }} />
            <Typography variant="h5" fontWeight={700} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <BookIcon /> Glossary
            </Typography>

            <TextField
                size="small"
                placeholder="Search glossary…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                sx={{ mb: 2, width: 320 }}
                InputProps={{
                    startAdornment: (
                        <InputAdornment position="start">
                            <SearchIcon fontSize="small" />
                        </InputAdornment>
                    ),
                }}
            />

            <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{ fontWeight: 700, width: 260 }}>Term</TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>Definition</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {filteredGlossary.map((g) => (
                            <TableRow key={g.term}>
                                <TableCell><strong>{g.term}</strong></TableCell>
                                <TableCell>{g.definition}</TableCell>
                            </TableRow>
                        ))}
                        {filteredGlossary.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={2}>
                                    <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                                        No matching glossary entries.
                                    </Typography>
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Container>
    );
}
