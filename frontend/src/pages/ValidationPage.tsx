import { useState, useEffect } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import {
  Box,
  Container,
  Typography,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  Chip,
  IconButton,
  LinearProgress,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Tooltip,
  Divider,
  Stepper,
  Step,
  StepLabel,
  FormGroup,
  FormControlLabel,
  Checkbox,
  TextField,
} from "@mui/material";
import {
  ArrowBack as BackIcon,
  Balance as FairnessIcon,
  Visibility as TransparencyIcon,
  Lock as PrivacyIcon,
  Assignment as AccountabilityIcon,
  CheckCircle as CheckIcon,
  Cancel as FailIcon,
  PlayArrow as RunIcon,
  Refresh as RefreshIcon,
  Info as InfoIcon,
  CheckBox as CheckBoxIcon,
  CheckBoxOutlineBlank as CheckBoxBlankIcon,
  ArrowForward as NextIcon,
  Lock as LockIcon,
} from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";
import {
  modelsApi,
  datasetsApi,
  validationApi,
  requirementsApi,
  reportsApi,
  templatesApi,
} from "../services/api";
import type { Template } from "../types";
import FairnessMetricDetail from "../components/FairnessMetricDetail";

// ─── Validator definitions ────────────────────────────────────────────────────
interface ValidatorDef {
  key: string;
  label: string;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  borderColor: string;
  shortDesc: string;
  longDesc: string;
  requiresSensitiveFeature?: boolean;
  requiresModel?: boolean;
}

const VALIDATORS: ValidatorDef[] = [
  {
    key: "fairness",
    label: "Fairness",
    icon: <FairnessIcon sx={{ fontSize: 40 }} />,
    color: "#2e7d32",
    bgColor: "#f1f8e9",
    borderColor: "#4caf50",
    shortDesc: "Bias & demographic parity",
    longDesc:
      "Checks whether the model treats different demographic groups equitably. " +
      "Computes Demographic Parity Ratio, Equalized Odds Ratio, and Disparate Impact Ratio using Fairlearn. " +
      "Requires a sensitive feature (e.g. gender, race) and optionally a target (ground truth) column. " +
      "Without a target column, fairness is measured using model predictions as a proxy. " +
      "New: if your dataset already contains a prediction column you can skip the model upload entirely — " +
      "select “Use predictions already in dataset” in the configuration step.",
    requiresSensitiveFeature: true,
    requiresModel: true,
  },
  {
    key: "transparency",
    label: "Transparency",
    icon: <TransparencyIcon sx={{ fontSize: 40 }} />,
    color: "#1565c0",
    bgColor: "#e3f2fd",
    borderColor: "#2196f3",
    shortDesc: "Explainability & feature importance",
    longDesc:
      "Explains how the model makes decisions using SHAP (SHapley Additive exPlanations) and LIME. " +
      "Ranks feature contributions for individual predictions and the overall model. " +
      "Generates a Model Card with performance metrics (accuracy, precision, recall, F1) and a Confusion Matrix. " +
      "Helps stakeholders understand which features drive outcomes.",
    requiresModel: true,
  },
  {
    key: "privacy",
    label: "Privacy",
    icon: <PrivacyIcon sx={{ fontSize: 40 }} />,
    color: "#e65100",
    bgColor: "#fff3e0",
    borderColor: "#ff9800",
    shortDesc: "PII detection & k-anonymity",
    longDesc:
      "Audits the dataset for privacy risks. " +
      "Detects Personally Identifiable Information (PII) such as names, emails, phone numbers, and SSNs. " +
      "Computes k-Anonymity to verify each individual is indistinguishable from at least k−1 others. " +
      "Optionally computes l-Diversity to ensure sensitive attribute variety within each equivalence class.",
  },
  {
    key: "accountability",
    label: "Accountability",
    icon: <AccountabilityIcon sx={{ fontSize: 40 }} />,
    color: "#6a1b9a",
    bgColor: "#f3e5f5",
    borderColor: "#9c27b0",
    shortDesc: "Audit trail & MLflow logging",
    longDesc:
      "Creates an immutable audit trail for every validation run via MLflow. " +
      "Logs model metadata, dataset fingerprints, all computed metrics, and pass/fail status. " +
      "Supports regulatory compliance by preserving a complete history of who ran which validation, when, and with what results. " +
      "When selected alongside other validators the audit is embedded automatically.",
  },
];

const STEPS = [
  "Select Validations",
  "Configure & Run",
  "Select Requirements",
  "Results",
];

const FAIRNESS_METRICS = [
  {
    key: "demographic_parity_ratio",
    label: "Demographic Parity Ratio",
    defaultThreshold: 0.8,
  },
  {
    key: "demographic_parity_difference",
    label: "Demographic Parity Difference",
    defaultThreshold: 0.1,
  },
  {
    key: "equalized_odds_ratio",
    label: "Equalized Odds Ratio",
    defaultThreshold: 0.8,
  },
  {
    key: "equalized_odds_difference",
    label: "Equalized Odds Difference",
    defaultThreshold: 0.1,
  },
  {
    key: "equal_opportunity_difference",
    label: "Equal Opportunity Difference",
    defaultThreshold: 0.05,
  },
  {
    key: "disparate_impact_ratio",
    label: "Disparate Impact Ratio",
    defaultThreshold: 0.8,
  },
];

const DEFAULT_FAIRNESS_METRICS = [
  "demographic_parity_ratio",
  "equalized_odds_ratio",
  "disparate_impact_ratio",
];

const DEFAULT_FAIRNESS_THRESHOLDS: Record<string, number> = {
  demographic_parity_ratio: 0.8,
  demographic_parity_difference: 0.1,
  equalized_odds_ratio: 0.8,
  equalized_odds_difference: 0.1,
  equal_opportunity_difference: 0.05,
  disparate_impact_ratio: 0.8,
};

const PRIVACY_CHECKS = [
  { key: "pii_detection", label: "PII Detection" },
  { key: "k_anonymity", label: "k-Anonymity" },
  { key: "l_diversity", label: "l-Diversity" },
  { key: "differential_privacy", label: "Differential Privacy (ε)" },
  { key: "hipaa", label: "HIPAA Safe Harbor" },
];

const DEFAULT_PRIVACY_CHECKS = ["pii_detection", "k_anonymity"];
const FAIRNESS_METRIC_KEYS = new Set(FAIRNESS_METRICS.map((m) => m.key));
const TRANSPARENCY_TEMPLATE_METRICS = new Set([
  "shap_coverage",
  "model_card_completeness",
  "explanation_required",
]);

const PassChip = ({ passed }: { passed: boolean }) => (
  <Chip
    label={passed ? "✓ Pass" : "✗ Fail"}
    color={passed ? "success" : "error"}
    size="small"
  />
);

export default function ValidationPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const viewSuiteId = searchParams.get("suite");

  // Wizard step: 0=select, 1=configure, 2=results
  const [activeStep, setActiveStep] = useState(0);

  // Validator selection
  const [selectedValidators, setSelectedValidators] = useState<string[]>([]);
  const [expandedValidator, setExpandedValidator] = useState<string | null>(
    null,
  );

  // Form fields
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedDataset, setSelectedDataset] = useState("");
  const [sensitiveFeature, setSensitiveFeature] = useState("");
  const [targetColumn, setTargetColumn] = useState("");
  const [quasiIdentifiers, setQuasiIdentifiers] = useState<string[]>([]);
  const [sensitiveAttribute, setSensitiveAttribute] = useState("");
  const [selectedFairnessMetrics, setSelectedFairnessMetrics] = useState<
    string[]
  >(DEFAULT_FAIRNESS_METRICS);
  const [fairnessThresholds, setFairnessThresholds] = useState<
    Record<string, number>
  >(DEFAULT_FAIRNESS_THRESHOLDS);
  const [selectedPrivacyChecks, setSelectedPrivacyChecks] = useState<string[]>(
    DEFAULT_PRIVACY_CHECKS,
  );
  const [kAnonymityK, setKAnonymityK] = useState<number>(5);
  const [lDiversityL, setLDiversityL] = useState<number>(2);
  const [dpTargetEpsilon, setDpTargetEpsilon] = useState<number>(1.0);
  const [dpApplyNoise, setDpApplyNoise] = useState<boolean>(false);
  const [formError, setFormError] = useState("");

  // Dataset-predictions mode (fairness without uploading a model)
  const [predictionMode, setPredictionMode] = useState<"model" | "dataset">(
    "model",
  );
  const [predictionColumn, setPredictionColumn] = useState("");
  const [actualColumn, setActualColumn] = useState("");

  // Requirements selection
  const [selectedRequirements, setSelectedRequirements] = useState<string[]>(
    [],
  );
  const [useRequirementThresholds, setUseRequirementThresholds] =
    useState(false);

  // Run state
  const [isRunning, setIsRunning] = useState(false);
  const [taskId, setTaskId] = useState("");
  const [suiteId, setSuiteId] = useState("");
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [results, setResults] = useState<any>(null);
  const [runError, setRunError] = useState("");

  // Warning dialog
  const [showWarningDialog, setShowWarningDialog] = useState(false);
  const [selectedFairnessMetric, setSelectedFairnessMetric] =
    useState<any>(null);

  // Load existing suite when navigated via ?suite=
  useEffect(() => {
    if (viewSuiteId) {
      (async () => {
        try {
          const suiteResults = await validationApi.getSuiteResults(viewSuiteId);
          setResults(suiteResults);
          setSuiteId(viewSuiteId);
          setActiveStep(3);
        } catch (err: any) {
          setRunError(err.message || "Failed to load validation results");
        }
      })();
    }
  }, [viewSuiteId]);

  const { data: models } = useQuery({
    queryKey: ["models", id],
    queryFn: () => modelsApi.list(id!),
    enabled: !!id,
  });
  const { data: datasets } = useQuery({
    queryKey: ["datasets", id],
    queryFn: () => datasetsApi.list(id!),
    enabled: !!id,
  });
  const { data: requirements } = useQuery({
    queryKey: ["requirements", id],
    queryFn: () => requirementsApi.listByProject(id!),
    enabled: !!id,
  });
  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates", "validation-presets"],
    queryFn: () => templatesApi.list(),
    enabled: !!id,
  });
  const selectedDatasetObj = datasets?.find(
    (d: any) => d.id === selectedDataset,
  );
  const isTemplatePresetActive = selectedTemplateId !== "";

  const applyTemplatePreset = (template: Template) => {
    const validatorSet = new Set<string>();
    const fairnessMetricSet = new Set<string>();
    const privacyCheckSet = new Set<string>();
    const newThresholds: Record<string, number> = {
      ...DEFAULT_FAIRNESS_THRESHOLDS,
    };
    let newK = 5;
    let newL = 2;

    (template.rules?.principles || []).forEach((p) => {
      const principle = (p || "").toLowerCase();
      if (
        ["fairness", "transparency", "privacy", "accountability"].includes(
          principle,
        )
      ) {
        validatorSet.add(principle);
      }
    });

    for (const item of template.rules?.items || []) {
      const metric = (item.metric || "").toLowerCase();
      const principle = (item.principle || "").toLowerCase();

      if (
        ["fairness", "transparency", "privacy", "accountability"].includes(
          principle,
        )
      ) {
        validatorSet.add(principle);
      }

      if (FAIRNESS_METRIC_KEYS.has(metric)) {
        validatorSet.add("fairness");
        fairnessMetricSet.add(metric);
        if (typeof item.value === "number") {
          newThresholds[metric] = item.value;
        }
      }

      if (TRANSPARENCY_TEMPLATE_METRICS.has(metric)) {
        validatorSet.add("transparency");
      }

      if (metric.includes("pii")) {
        validatorSet.add("privacy");
        privacyCheckSet.add("pii_detection");
      }

      if (["k_anonymity", "k_anonymity_k", "k_value"].includes(metric)) {
        validatorSet.add("privacy");
        privacyCheckSet.add("k_anonymity");
        if (typeof item.value === "number") {
          newK = Math.max(1, Math.round(item.value));
        }
      }

      if (["l_diversity", "l_diversity_l", "l_value"].includes(metric)) {
        validatorSet.add("privacy");
        privacyCheckSet.add("l_diversity");
        if (typeof item.value === "number") {
          newL = Math.max(1, Math.round(item.value));
        }
      }

      if (metric === "audit_trail_required") {
        validatorSet.add("accountability");
      }
    }

    const validators = Array.from(validatorSet);
    const fairnessMetrics =
      fairnessMetricSet.size > 0
        ? Array.from(fairnessMetricSet)
        : DEFAULT_FAIRNESS_METRICS;
    const privacyChecks =
      privacyCheckSet.size > 0
        ? Array.from(privacyCheckSet)
        : DEFAULT_PRIVACY_CHECKS;

    setSelectedValidators(validators);
    setSelectedFairnessMetrics(fairnessMetrics);
    setFairnessThresholds(newThresholds);
    setSelectedPrivacyChecks(privacyChecks);
    setKAnonymityK(newK);
    setLDiversityL(newL);
    setSelectedRequirements([]);
    setUseRequirementThresholds(false);
  };

  // Poll task
  useEffect(() => {
    if (!taskId || !isRunning) return;
    const interval = setInterval(async () => {
      try {
        const status = await validationApi.getTaskStatus(taskId);
        setProgress(status.progress ?? 0);
        setCurrentStep(status.current_step || "");
        if (status.state === "SUCCESS") {
          if (suiteId) {
            const suiteResults = await validationApi.getSuiteResults(suiteId);
            setResults(suiteResults);
          }
          setIsRunning(false);
          setActiveStep(3);
          clearInterval(interval);
        } else if (status.state === "FAILURE") {
          setRunError(status.error || "Validation failed");
          setIsRunning(false);
          clearInterval(interval);
        }
      } catch (err: any) {
        setRunError(err.message);
        setIsRunning(false);
        clearInterval(interval);
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [taskId, isRunning, suiteId]);

  const toggleValidator = (key: string) => {
    if (isTemplatePresetActive) return;
    setSelectedValidators((prev) =>
      prev.includes(key) ? prev.filter((v) => v !== key) : [...prev, key],
    );
  };

  const toggleFairnessMetric = (metric: string) => {
    if (isTemplatePresetActive) return;
    setSelectedFairnessMetrics((prev) =>
      prev.includes(metric)
        ? prev.filter((m) => m !== metric)
        : [...prev, metric],
    );
  };

  const togglePrivacyCheck = (check: string) => {
    if (isTemplatePresetActive) return;
    setSelectedPrivacyChecks((prev) =>
      prev.includes(check) ? prev.filter((c) => c !== check) : [...prev, check],
    );
  };

  const needsSensitiveFeature = selectedValidators.includes("fairness");
  const needsModel =
    selectedValidators.includes("transparency") ||
    (selectedValidators.includes("fairness") && predictionMode === "model");
  const needsQuasiIdentifiers =
    selectedPrivacyChecks.includes("k_anonymity") ||
    selectedPrivacyChecks.includes("l_diversity");
  const needsSensitiveAttribute = selectedPrivacyChecks.includes("l_diversity");

  const validateConfig = () => {
    if (!selectedDataset) return "Please select a dataset.";
    if (needsModel && !selectedModel)
      return "Please select a model (required for Fairness / Transparency).";
    if (needsSensitiveFeature && !sensitiveFeature)
      return "Please select a Sensitive Feature (required for Fairness).";
    if (
      selectedValidators.includes("fairness") &&
      predictionMode === "dataset" &&
      !predictionColumn
    ) {
      return "Please select the Prediction Column (the column in your dataset that holds model predictions).";
    }
    if (
      selectedValidators.includes("fairness") &&
      selectedFairnessMetrics.length === 0
    ) {
      return "Please select at least one fairness metric.";
    }
    if (
      selectedValidators.includes("privacy") &&
      selectedPrivacyChecks.length === 0
    ) {
      return "Please select at least one privacy check.";
    }
    if (
      selectedValidators.includes("privacy") &&
      selectedPrivacyChecks.includes("k_anonymity") &&
      quasiIdentifiers.length === 0
    ) {
      return "Please select Quasi-Identifiers for k-anonymity.";
    }
    if (
      selectedValidators.includes("privacy") &&
      selectedPrivacyChecks.includes("l_diversity")
    ) {
      if (quasiIdentifiers.length === 0)
        return "Please select Quasi-Identifiers for l-diversity.";
      if (!sensitiveAttribute)
        return "Please select Sensitive Attribute for l-diversity.";
    }
    return "";
  };

  // Filter requirements by selected validators' principles
  const relevantRequirements = (requirements || []).filter(
    (r: any) =>
      selectedValidators.includes(r.principle) && r.status !== "archived",
  );

  const toggleRequirement = (reqId: string) =>
    setSelectedRequirements((prev) =>
      prev.includes(reqId)
        ? prev.filter((id) => id !== reqId)
        : [...prev, reqId],
    );

  // Apply thresholds from selected requirements to fairness/privacy config
  const applyRequirementThresholds = () => {
    const selected = (requirements || []).filter((r: any) =>
      selectedRequirements.includes(r.id),
    );
    const newThresholds = { ...fairnessThresholds };
    let newK = kAnonymityK;
    let newL = lDiversityL;

    for (const req of selected) {
      const rules = req.specification?.rules || [];
      for (const rule of rules) {
        // For fairness metrics
        if (rule.metric && newThresholds[rule.metric] !== undefined) {
          newThresholds[rule.metric] = rule.value;
        }
        // For privacy thresholds
        if (rule.metric === "k_anonymity_k" || rule.metric === "k_value") {
          newK = rule.value;
        }
        if (rule.metric === "l_diversity_l" || rule.metric === "l_value") {
          newL = rule.value;
        }
      }
    }

    setFairnessThresholds(newThresholds);
    setKAnonymityK(newK);
    setLDiversityL(newL);
    setUseRequirementThresholds(true);
  };

  const handleRun = async (skipWarning = false) => {
    const configErr = validateConfig();
    if (configErr) {
      setFormError(configErr);
      return;
    }
    setFormError("");
    if (
      !skipWarning &&
      selectedValidators.includes("fairness") &&
      predictionMode === "model" &&
      !targetColumn
    ) {
      setShowWarningDialog(true);
      return;
    }
    setIsRunning(true);
    setProgress(0);
    setCurrentStep("Queuing validations…");
    setRunError("");
    try {
      const effectiveSelectedValidators = selectedValidators.filter(
        (v) => v !== "transparency" || !!targetColumn,
      );

      // Dataset-predictions fairness mode: call the dedicated endpoint directly
      if (
        predictionMode === "dataset" &&
        selectedValidators.includes("fairness") &&
        selectedValidators.length === 1
      ) {
        setCurrentStep("Running fairness from dataset predictions…");
        const fairnessResult = await validationApi.fairnessFromPredictions({
          dataset_id: selectedDataset,
          sensitive_feature: sensitiveFeature,
          prediction_column: predictionColumn,
          actual_column: actualColumn || null,
          selected_metrics: selectedFairnessMetrics,
          thresholds: selectedFairnessMetrics.reduce(
            (acc, m) => {
              acc[m] = fairnessThresholds[m];
              return acc;
            },
            {} as Record<string, number>,
          ),
        });
        // Wrap the result in a pseudo-suite shape so results render correctly
        setResults({
          suite_id: null,
          overall_passed: fairnessResult.overall_passed,
          validations: [
            {
              type: "fairness",
              status: "completed",
              passed: fairnessResult.overall_passed,
              validation_id: fairnessResult.validation_id,
              result: fairnessResult,
            },
          ],
        });
        setProgress(100);
        setCurrentStep("Completed");
        setIsRunning(false);
        setActiveStep(3);
        return;
      }

      const response = await validationApi.runAll({
        model_id: selectedModel,
        dataset_id: selectedDataset,
        selected_validations: effectiveSelectedValidators,
        fairness_config: {
          sensitive_feature: sensitiveFeature,
          target_column: targetColumn || null,
          selected_metrics: selectedFairnessMetrics,
          thresholds: selectedFairnessMetrics.reduce(
            (acc, metricName) => {
              acc[metricName] = fairnessThresholds[metricName];
              return acc;
            },
            {} as Record<string, number>,
          ),
        },
        transparency_config: {
          target_column: targetColumn || null,
          sample_size: 100,
        },
        privacy_config: {
          selected_checks: selectedPrivacyChecks,
          k_anonymity_k: kAnonymityK,
          l_diversity_l: lDiversityL,
          quasi_identifiers:
            quasiIdentifiers.length > 0 ? quasiIdentifiers : undefined,
          sensitive_attribute: sensitiveAttribute || undefined,
          dp_target_epsilon: dpTargetEpsilon,
          dp_apply_noise: dpApplyNoise,
        },
        requirement_ids:
          selectedRequirements.length > 0 ? selectedRequirements : undefined,
      });
      setTaskId(response.task_id);
      setSuiteId(response.suite_id);
      setCurrentStep("Validation suite queued");
    } catch (err: any) {
      setRunError(err.response?.data?.detail || err.message);
      setIsRunning(false);
    }
  };

  const handleReset = () => {
    setActiveStep(0);
    setSelectedTemplateId("");
    setSelectedValidators([]);
    setExpandedValidator(null);
    setSelectedModel("");
    setSelectedDataset("");
    setSensitiveFeature("");
    setTargetColumn("");
    setQuasiIdentifiers([]);
    setSensitiveAttribute("");
    setSelectedFairnessMetrics(DEFAULT_FAIRNESS_METRICS);
    setFairnessThresholds(DEFAULT_FAIRNESS_THRESHOLDS);
    setSelectedPrivacyChecks(DEFAULT_PRIVACY_CHECKS);
    setKAnonymityK(5);
    setLDiversityL(2);
    setSelectedRequirements([]);
    setUseRequirementThresholds(false);
    setPredictionMode("model");
    setPredictionColumn("");
    setActualColumn("");
    setIsRunning(false);
    setTaskId("");
    setSuiteId("");
    setProgress(0);
    setCurrentStep("");
    setResults(null);
    setRunError("");
    setFormError("");
  };

  const handleDownloadSuitePdf = async () => {
    const activeSuiteId = results?.suite_id || suiteId;
    if (!activeSuiteId) return;
    try {
      const blob = await reportsApi.downloadValidationPdf(activeSuiteId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `validation_report_${activeSuiteId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setRunError(err?.message || "Failed to download PDF report");
    }
  };

  return (
    <>
      {/* No-target warning */}
      <Dialog
        open={showWarningDialog}
        onClose={() => setShowWarningDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle
          sx={{ bgcolor: "warning.main", color: "warning.contrastText" }}
        >
          ⚠️ No Target Column Specified
        </DialogTitle>
        <DialogContent sx={{ mt: 2 }}>
          <DialogContentText>
            Without a target column, fairness analysis uses{" "}
            <strong>model predictions as ground truth</strong>. Results may be
            misleading.
          </DialogContentText>
          <Box component="ul" sx={{ mt: 1, pl: 2 }}>
            <li>
              <DialogContentText>
                Accuracy-based metrics won't reflect real-world performance
              </DialogContentText>
            </li>
            <li>
              <DialogContentText>
                Only internal prediction consistency is checked
              </DialogContentText>
            </li>
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button
            variant="outlined"
            onClick={() => setShowWarningDialog(false)}
          >
            Cancel – Add Target Column
          </Button>
          <Button
            variant="contained"
            color="warning"
            onClick={() => {
              setShowWarningDialog(false);
              handleRun(true);
            }}
          >
            Proceed Anyway
          </Button>
        </DialogActions>
      </Dialog>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ display: "flex", alignItems: "center", mb: 3 }}>
          <IconButton
            onClick={() => navigate(`/projects/${id}`)}
            sx={{ mr: 2 }}
          >
            <BackIcon />
          </IconButton>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
              Ethical AI Validation Suite
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Choose which validations to run — individually or in any
              combination
            </Typography>
          </Box>
        </Box>

        {/* Stepper */}
        {!viewSuiteId && (
          <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
            {STEPS.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        )}

        {runError && (
          <Alert
            severity="error"
            sx={{ mb: 3 }}
            onClose={() => setRunError("")}
          >
            {runError}
          </Alert>
        )}

        {/* ── STEP 0: SELECT VALIDATORS ──────────────────────────────── */}
        {activeStep === 0 && (
          <Box>
            {/* Quick usage guide */}
            <Alert severity="info" icon={false} sx={{ mb: 2, py: 1 }}>
              <Typography variant="body2">
                <strong>How to use this page:</strong>&ensp;
                <strong>Step 1</strong> — tick the validations you want
                (Fairness, Transparency, Privacy, Accountability). &ensp;
                <strong>Step 2</strong> — pick your model &amp; dataset and tune
                thresholds. &ensp;<strong>Step 3</strong> — optionally link
                saved requirements whose thresholds will override defaults.
                &ensp;<strong>Step 4</strong> — view pass/fail results and
                download a PDF report.
              </Typography>
            </Alert>
            <Box sx={{ display: "flex", gap: 1, mb: 2, alignItems: "center" }}>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ flex: 1 }}
              >
                Click a card to select it. Press the{" "}
                <InfoIcon sx={{ fontSize: 14, verticalAlign: "middle" }} /> icon
                for a full description.
              </Typography>
              <Button
                size="small"
                startIcon={<CheckBoxIcon />}
                disabled={isTemplatePresetActive}
                onClick={() =>
                  setSelectedValidators(VALIDATORS.map((v) => v.key))
                }
              >
                Select All
              </Button>
              <Button
                size="small"
                startIcon={<CheckBoxBlankIcon />}
                color="inherit"
                disabled={isTemplatePresetActive}
                onClick={() => setSelectedValidators([])}
              >
                Clear
              </Button>
            </Box>

            <Card variant="outlined" sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
                  Template Preset (Optional)
                </Typography>
                <FormControl fullWidth>
                  <InputLabel>Select Template</InputLabel>
                  <Select
                    value={selectedTemplateId}
                    label="Select Template"
                    onChange={(e) => {
                      const templateId = e.target.value;
                      setSelectedTemplateId(templateId);
                      if (!templateId) return;
                      const preset = templates.find(
                        (tpl) => tpl.id === templateId,
                      );
                      if (preset) {
                        applyTemplatePreset(preset);
                      }
                    }}
                  >
                    <MenuItem value="">
                      <em>No template preset (manual)</em>
                    </MenuItem>
                    {templates.map((tpl) => (
                      <MenuItem key={tpl.id} value={tpl.id}>
                        <Box
                          sx={{
                            width: "100%",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 1,
                          }}
                        >
                          <Typography
                            variant="body2"
                            sx={{
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            {tpl.name}
                          </Typography>
                          <Chip
                            size="small"
                            label={`${tpl.rules?.items?.length ?? 0}`}
                            variant="outlined"
                            color="primary"
                            sx={{ minWidth: 36, justifyContent: "center" }}
                          />
                        </Box>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {isTemplatePresetActive && (
                  <Alert severity="info" sx={{ mt: 1.5 }}>
                    Template preset applied: validation types and metrics are
                    auto-configured. Continue to choose model, dataset, and
                    dataset columns.
                  </Alert>
                )}
              </CardContent>
            </Card>

            {/* Validator grid */}
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
                gap: 2.5,
                mb: 3,
              }}
            >
              {VALIDATORS.map((v) => {
                const isSelected = selectedValidators.includes(v.key);
                const isExpanded = expandedValidator === v.key;
                return (
                  <Card
                    key={v.key}
                    elevation={isSelected ? 4 : 1}
                    onClick={() => toggleValidator(v.key)}
                    sx={{
                      border: "2px solid",
                      borderColor: isSelected ? v.borderColor : "divider",
                      bgcolor: isSelected ? v.bgColor : "background.paper",
                      transition: "all 0.2s ease",
                      cursor: isTemplatePresetActive
                        ? "not-allowed"
                        : "pointer",
                      opacity: 1,
                      "&:hover": { borderColor: v.borderColor, boxShadow: 4 },
                    }}
                  >
                    <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 1.5,
                        }}
                      >
                        {/* Checkbox */}
                        <Box
                          sx={{
                            color: isSelected ? v.color : "text.disabled",
                            mt: 0.2,
                            flexShrink: 0,
                          }}
                        >
                          {isSelected ? (
                            <CheckBoxIcon />
                          ) : (
                            <CheckBoxBlankIcon />
                          )}
                        </Box>
                        {/* Icon + text */}
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 1.5,
                              mb: isExpanded ? 0 : 0,
                            }}
                          >
                            <Box sx={{ color: v.color }}>{v.icon}</Box>
                            <Box>
                              <Typography
                                variant="h6"
                                sx={{
                                  fontWeight: 700,
                                  color: v.color,
                                  lineHeight: 1.2,
                                }}
                              >
                                {v.label}
                              </Typography>
                              <Typography
                                variant="body2"
                                sx={{
                                  color: isSelected
                                    ? "rgba(12, 20, 28, 0.86)"
                                    : "text.secondary",
                                }}
                              >
                                {v.shortDesc}
                              </Typography>
                              <Box
                                sx={{
                                  display: "flex",
                                  gap: 0.5,
                                  mt: 0.5,
                                  flexWrap: "wrap",
                                }}
                              >
                                {v.requiresModel && (
                                  <Chip
                                    label="Needs model"
                                    size="small"
                                    variant="outlined"
                                    sx={{
                                      fontSize: "0.65rem",
                                      height: 18,
                                      color: isSelected
                                        ? "rgba(12, 20, 28, 0.78)"
                                        : "text.secondary",
                                      borderColor: isSelected
                                        ? "rgba(12, 20, 28, 0.28)"
                                        : "divider",
                                    }}
                                  />
                                )}
                                {v.requiresSensitiveFeature && (
                                  <Chip
                                    label="Sensitive column"
                                    size="small"
                                    variant="outlined"
                                    sx={{
                                      fontSize: "0.65rem",
                                      height: 18,
                                      color: isSelected
                                        ? "rgba(12, 20, 28, 0.78)"
                                        : "text.secondary",
                                      borderColor: isSelected
                                        ? "rgba(12, 20, 28, 0.28)"
                                        : "divider",
                                    }}
                                  />
                                )}
                                {isTemplatePresetActive && (
                                  <Chip
                                    icon={<LockIcon sx={{ fontSize: 12 }} />}
                                    label="Locked by template"
                                    size="small"
                                    color="default"
                                    variant="outlined"
                                    sx={{
                                      fontSize: "0.65rem",
                                      height: 18,
                                      color: isSelected
                                        ? "rgba(12, 20, 28, 0.78)"
                                        : "text.secondary",
                                      borderColor: isSelected
                                        ? "rgba(12, 20, 28, 0.28)"
                                        : "divider",
                                    }}
                                  />
                                )}
                              </Box>
                            </Box>
                          </Box>
                          {isExpanded && (
                            <Typography
                              variant="body2"
                              sx={{
                                mt: 1.5,
                                color: isSelected
                                  ? "rgba(12, 20, 28, 0.78)"
                                  : "text.secondary",
                                lineHeight: 1.65,
                                borderTop: "1px solid",
                                borderColor: isSelected
                                  ? "rgba(12, 20, 28, 0.18)"
                                  : "divider",
                                pt: 1.5,
                              }}
                            >
                              {v.longDesc}
                            </Typography>
                          )}
                        </Box>
                        {/* Info toggle */}
                        <Tooltip
                          title={isExpanded ? "Hide details" : "Show details"}
                        >
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              setExpandedValidator(isExpanded ? null : v.key);
                            }}
                            sx={{
                              color: isExpanded
                                ? v.color
                                : isSelected
                                  ? "rgba(12, 20, 28, 0.58)"
                                  : "text.disabled",
                              flexShrink: 0,
                            }}
                          >
                            <InfoIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </CardContent>
                  </Card>
                );
              })}
            </Box>

            {/* Selected chips */}
            {selectedValidators.length > 0 && (
              <Paper
                variant="outlined"
                sx={{
                  p: 2,
                  mb: 3,
                  display: "flex",
                  alignItems: "center",
                  gap: 1.5,
                  flexWrap: "wrap",
                }}
              >
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Selected:
                </Typography>
                {selectedValidators.map((key) => {
                  const v = VALIDATORS.find((d) => d.key === key)!;
                  return (
                    <Chip
                      key={key}
                      label={v.label}
                      size="small"
                      onDelete={() => toggleValidator(key)}
                      sx={{
                        bgcolor: v.bgColor,
                        color: v.color,
                        fontWeight: 600,
                        border: `1px solid ${v.borderColor}`,
                      }}
                    />
                  );
                })}
              </Paper>
            )}

            <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
              <Button
                variant="contained"
                size="large"
                disabled={selectedValidators.length === 0}
                endIcon={<NextIcon />}
                onClick={() => setActiveStep(1)}
              >
                Next: Configure
              </Button>
            </Box>
          </Box>
        )}

        {/* ── STEP 1: CONFIGURE ──────────────────────────────────────── */}
        {activeStep === 1 && !isRunning && (
          <Card>
            <CardContent sx={{ p: 4 }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 700 }}>
                Configure Validation Parameters
              </Typography>

              {/* Reminder chips */}
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 3 }}>
                {selectedValidators.map((key) => {
                  const v = VALIDATORS.find((d) => d.key === key)!;
                  return (
                    <Chip
                      key={key}
                      label={v.label}
                      size="small"
                      sx={{
                        bgcolor: v.bgColor,
                        color: v.color,
                        fontWeight: 600,
                        border: `1px solid ${v.borderColor}`,
                      }}
                    />
                  );
                })}
              </Box>

              {isTemplatePresetActive && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  Template preset is active. Validation metrics/checks and
                  thresholds are locked to template defaults.
                </Alert>
              )}

              {formError && (
                <Alert
                  severity="error"
                  sx={{ mb: 2 }}
                  onClose={() => setFormError("")}
                >
                  {formError}
                </Alert>
              )}

              <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
                {/* Dataset — always */}
                <Box>
                  <Typography
                    variant="subtitle2"
                    sx={{ mb: 1, fontWeight: 600 }}
                  >
                    Dataset <span style={{ color: "red" }}>*</span>
                  </Typography>
                  <FormControl fullWidth>
                    <InputLabel>Select Dataset</InputLabel>
                    <Select
                      value={selectedDataset}
                      label="Select Dataset"
                      onChange={(e) => setSelectedDataset(e.target.value)}
                    >
                      {datasets?.map((d: any) => (
                        <MenuItem key={d.id} value={d.id}>
                          {d.name} ({d.row_count} rows)
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Box>

                {/* Model — only if fairness(model mode)/transparency selected */}
                {needsModel && (
                  <Box>
                    <Typography
                      variant="subtitle2"
                      sx={{ mb: 1, fontWeight: 600 }}
                    >
                      Model <span style={{ color: "red" }}>*</span>
                      <Typography
                        component="span"
                        variant="caption"
                        color="text.secondary"
                        sx={{ ml: 1 }}
                      >
                        {selectedValidators.includes("transparency") &&
                        !selectedValidators.includes("fairness")
                          ? "(required for Transparency)"
                          : selectedValidators.includes("fairness") &&
                              predictionMode === "model"
                            ? "(required for Fairness / Transparency)"
                            : "(required for Transparency)"}
                      </Typography>
                    </Typography>
                    <FormControl fullWidth>
                      <InputLabel>Select Model</InputLabel>
                      <Select
                        value={selectedModel}
                        label="Select Model"
                        onChange={(e) => setSelectedModel(e.target.value)}
                      >
                        {models?.map((m: any) => (
                          <MenuItem key={m.id} value={m.id}>
                            {m.name} ({m.model_type})
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>
                )}

                {/* Fairness fields */}
                {selectedValidators.includes("fairness") && (
                  <>
                    <Divider>
                      <Chip
                        label="Fairness Settings"
                        size="small"
                        sx={{ bgcolor: "#e8f5e9", color: "#2e7d32" }}
                      />
                    </Divider>

                    {/* Prediction source toggle */}
                    <Box>
                      <Typography
                        variant="subtitle2"
                        sx={{ mb: 1, fontWeight: 600 }}
                      >
                        Prediction Source
                      </Typography>
                      <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
                        <Button
                          variant={
                            predictionMode === "model"
                              ? "contained"
                              : "outlined"
                          }
                          size="small"
                          onClick={() => setPredictionMode("model")}
                          sx={{ textTransform: "none" }}
                        >
                          Run predictions with uploaded model
                        </Button>
                        <Button
                          variant={
                            predictionMode === "dataset"
                              ? "contained"
                              : "outlined"
                          }
                          color="secondary"
                          size="small"
                          onClick={() => setPredictionMode("dataset")}
                          sx={{ textTransform: "none" }}
                        >
                          Use predictions already in dataset
                        </Button>
                      </Box>
                      {predictionMode === "dataset" &&
                        selectedValidators.length > 1 && (
                          <Alert severity="warning" sx={{ mt: 1 }}>
                            Dataset-predictions mode supports Fairness only.
                            Either deselect other validators or switch back to
                            model mode.
                          </Alert>
                        )}
                    </Box>

                    {/* Prediction column selectors (dataset mode) */}
                    {predictionMode === "dataset" && (
                      <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                        <Box sx={{ flex: "1 1 45%", minWidth: 240 }}>
                          <Typography
                            variant="subtitle2"
                            sx={{ mb: 1, fontWeight: 600 }}
                          >
                            Prediction Column{" "}
                            <span style={{ color: "red" }}>*</span>
                            <Typography
                              component="span"
                              variant="caption"
                              color="text.secondary"
                              sx={{ ml: 1 }}
                            >
                              (column holding predicted labels)
                            </Typography>
                          </Typography>
                          <FormControl fullWidth>
                            <InputLabel>Select column</InputLabel>
                            <Select
                              value={predictionColumn}
                              label="Select column"
                              onChange={(e) =>
                                setPredictionColumn(e.target.value)
                              }
                              disabled={!selectedDataset}
                            >
                              {selectedDatasetObj?.columns?.map(
                                (col: string) => (
                                  <MenuItem key={col} value={col}>
                                    {col}
                                  </MenuItem>
                                ),
                              )}
                            </Select>
                          </FormControl>
                        </Box>
                        <Box sx={{ flex: "1 1 45%", minWidth: 240 }}>
                          <Typography
                            variant="subtitle2"
                            sx={{ mb: 1, fontWeight: 600 }}
                          >
                            Actual / Ground-Truth Column
                            <Typography
                              component="span"
                              variant="caption"
                              color="text.secondary"
                              sx={{ ml: 1 }}
                            >
                              (optional – unlocks more metrics)
                            </Typography>
                          </Typography>
                          <FormControl fullWidth>
                            <InputLabel>Select column</InputLabel>
                            <Select
                              value={actualColumn}
                              label="Select column"
                              onChange={(e) => setActualColumn(e.target.value)}
                              disabled={!selectedDataset}
                            >
                              <MenuItem value="">
                                <em>None</em>
                              </MenuItem>
                              {selectedDatasetObj?.columns?.map(
                                (col: string) => (
                                  <MenuItem key={col} value={col}>
                                    {col}
                                  </MenuItem>
                                ),
                              )}
                            </Select>
                          </FormControl>
                        </Box>
                      </Box>
                    )}

                    <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                      <Box sx={{ flex: "1 1 45%", minWidth: 240 }}>
                        <Typography
                          variant="subtitle2"
                          sx={{ mb: 1, fontWeight: 600 }}
                        >
                          Sensitive Feature{" "}
                          <span style={{ color: "red" }}>*</span>
                          <Typography
                            component="span"
                            variant="caption"
                            color="text.secondary"
                            sx={{ ml: 1 }}
                          >
                            (e.g. gender, race)
                          </Typography>
                        </Typography>
                        <FormControl fullWidth>
                          <InputLabel>Select column</InputLabel>
                          <Select
                            value={sensitiveFeature}
                            label="Select column"
                            onChange={(e) =>
                              setSensitiveFeature(e.target.value)
                            }
                            disabled={!selectedDataset}
                          >
                            {selectedDatasetObj?.columns?.map((col: string) => (
                              <MenuItem key={col} value={col}>
                                {col}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Box>
                      {predictionMode === "model" && (
                        <Box sx={{ flex: "1 1 45%", minWidth: 240 }}>
                          <Typography
                            variant="subtitle2"
                            sx={{ mb: 1, fontWeight: 600 }}
                          >
                            Target Column
                            <Typography
                              component="span"
                              variant="caption"
                              color="text.secondary"
                              sx={{ ml: 1 }}
                            >
                              (optional – ground truth labels)
                            </Typography>
                          </Typography>
                          <FormControl fullWidth>
                            <InputLabel>Target Column</InputLabel>
                            <Select
                              value={targetColumn}
                              label="Target Column"
                              onChange={(e) => setTargetColumn(e.target.value)}
                              disabled={!selectedDataset}
                            >
                              <MenuItem value="">
                                <em>None – use model predictions</em>
                              </MenuItem>
                              {selectedDatasetObj?.columns?.map(
                                (col: string) => (
                                  <MenuItem key={col} value={col}>
                                    {col}
                                  </MenuItem>
                                ),
                              )}
                            </Select>
                          </FormControl>
                          {!targetColumn && (
                            <Typography
                              variant="caption"
                              color="warning.main"
                              sx={{ mt: 0.5, display: "block" }}
                            >
                              ⚠️ Without a target column, predictions are used
                              as ground truth
                            </Typography>
                          )}
                        </Box>
                      )}
                    </Box>

                    <Box>
                      <Typography
                        variant="subtitle2"
                        sx={{ mb: 1, fontWeight: 600 }}
                      >
                        Fairness Metrics to Run
                      </Typography>
                      <FormGroup row>
                        {FAIRNESS_METRICS.map((metric) => (
                          <FormControlLabel
                            key={metric.key}
                            control={
                              <Checkbox
                                checked={selectedFairnessMetrics.includes(
                                  metric.key,
                                )}
                                disabled={isTemplatePresetActive}
                                onChange={() =>
                                  toggleFairnessMetric(metric.key)
                                }
                              />
                            }
                            label={metric.label}
                          />
                        ))}
                      </FormGroup>
                    </Box>

                    {selectedFairnessMetrics.length > 0 && (
                      <Box>
                        <Typography
                          variant="subtitle2"
                          sx={{ mb: 1, fontWeight: 600 }}
                        >
                          Thresholds (editable)
                        </Typography>
                        <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                          {FAIRNESS_METRICS.filter((metric) =>
                            selectedFairnessMetrics.includes(metric.key),
                          ).map((metric) => (
                            <TextField
                              key={metric.key}
                              label={metric.label}
                              type="number"
                              size="small"
                              value={
                                fairnessThresholds[metric.key] ??
                                metric.defaultThreshold
                              }
                              onChange={(e) =>
                                setFairnessThresholds((prev) => ({
                                  ...prev,
                                  [metric.key]: Number(e.target.value),
                                }))
                              }
                              disabled={isTemplatePresetActive}
                              inputProps={{ step: 0.01 }}
                              sx={{ minWidth: 280 }}
                            />
                          ))}
                        </Box>
                      </Box>
                    )}
                  </>
                )}

                {/* Privacy fields */}
                {selectedValidators.includes("privacy") && (
                  <>
                    <Divider>
                      <Chip
                        label="Privacy Settings"
                        size="small"
                        sx={{ bgcolor: "#fff3e0", color: "#e65100" }}
                      />
                    </Divider>
                    <Box>
                      <Typography
                        variant="subtitle2"
                        sx={{ mb: 1, fontWeight: 600 }}
                      >
                        Privacy Checks to Run
                      </Typography>
                      <FormGroup row>
                        {PRIVACY_CHECKS.map((check) => (
                          <FormControlLabel
                            key={check.key}
                            control={
                              <Checkbox
                                checked={selectedPrivacyChecks.includes(
                                  check.key,
                                )}
                                disabled={isTemplatePresetActive}
                                onChange={() => togglePrivacyCheck(check.key)}
                              />
                            }
                            label={check.label}
                          />
                        ))}
                      </FormGroup>
                    </Box>

                    <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                      <Box sx={{ flex: "1 1 45%", minWidth: 240 }}>
                        <Typography
                          variant="subtitle2"
                          sx={{ mb: 1, fontWeight: 600 }}
                        >
                          Quasi-Identifiers
                          <Typography
                            component="span"
                            variant="caption"
                            color="text.secondary"
                            sx={{ ml: 1 }}
                          >
                            (
                            {needsQuasiIdentifiers
                              ? "required by selected checks"
                              : "enable k-anonymity or l-diversity"}
                            )
                          </Typography>
                        </Typography>
                        <FormControl fullWidth>
                          <InputLabel>Select columns</InputLabel>
                          <Select
                            multiple
                            value={quasiIdentifiers}
                            label="Select columns"
                            onChange={(e) =>
                              setQuasiIdentifiers(e.target.value as string[])
                            }
                            disabled={
                              !selectedDataset || !needsQuasiIdentifiers
                            }
                            renderValue={(selected) => (
                              <Box
                                sx={{
                                  display: "flex",
                                  flexWrap: "wrap",
                                  gap: 0.5,
                                }}
                              >
                                {selected.map((val) => (
                                  <Chip key={val} label={val} size="small" />
                                ))}
                              </Box>
                            )}
                          >
                            {selectedDatasetObj?.columns?.map((col: string) => (
                              <MenuItem key={col} value={col}>
                                {col}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Box>

                      {selectedPrivacyChecks.includes("k_anonymity") && (
                        <Box sx={{ flex: "1 1 20%", minWidth: 180 }}>
                          <Typography
                            variant="subtitle2"
                            sx={{ mb: 1, fontWeight: 600 }}
                          >
                            k value
                          </Typography>
                          <TextField
                            fullWidth
                            size="small"
                            type="number"
                            value={kAnonymityK}
                            onChange={(e) =>
                              setKAnonymityK(Number(e.target.value))
                            }
                            disabled={isTemplatePresetActive}
                            inputProps={{ min: 1, step: 1 }}
                          />
                        </Box>
                      )}

                      <Box sx={{ flex: "1 1 45%", minWidth: 240 }}>
                        <Typography
                          variant="subtitle2"
                          sx={{ mb: 1, fontWeight: 600 }}
                        >
                          Sensitive Attribute
                          <Typography
                            component="span"
                            variant="caption"
                            color="text.secondary"
                            sx={{ ml: 1 }}
                          >
                            (
                            {needsSensitiveAttribute
                              ? "required for l-diversity"
                              : "enable l-diversity to edit"}
                            )
                          </Typography>
                        </Typography>
                        <FormControl fullWidth>
                          <InputLabel>Select column</InputLabel>
                          <Select
                            value={sensitiveAttribute}
                            label="Select column"
                            onChange={(e) =>
                              setSensitiveAttribute(e.target.value)
                            }
                            disabled={
                              !selectedDataset || !needsSensitiveAttribute
                            }
                          >
                            <MenuItem value="">None</MenuItem>
                            {selectedDatasetObj?.columns?.map((col: string) => (
                              <MenuItem key={col} value={col}>
                                {col}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Box>

                      {selectedPrivacyChecks.includes("l_diversity") && (
                        <Box sx={{ flex: "1 1 20%", minWidth: 180 }}>
                          <Typography
                            variant="subtitle2"
                            sx={{ mb: 1, fontWeight: 600 }}
                          >
                            l value
                          </Typography>
                          <TextField
                            fullWidth
                            size="small"
                            type="number"
                            value={lDiversityL}
                            onChange={(e) =>
                              setLDiversityL(Number(e.target.value))
                            }
                            disabled={isTemplatePresetActive}
                            inputProps={{ min: 1, step: 1 }}
                          />
                        </Box>
                      )}
                    </Box>

                    {/* Differential Privacy config */}
                    {selectedPrivacyChecks.includes("differential_privacy") && (
                      <Box
                        sx={{
                          display: "flex",
                          gap: 2,
                          mt: 2,
                          flexWrap: "wrap",
                        }}
                      >
                        <Box sx={{ flex: "1 1 30%", minWidth: 180 }}>
                          <Typography
                            variant="subtitle2"
                            sx={{ mb: 1, fontWeight: 600 }}
                          >
                            Target ε (epsilon)
                          </Typography>
                          <TextField
                            fullWidth
                            size="small"
                            type="number"
                            value={dpTargetEpsilon}
                            onChange={(e) =>
                              setDpTargetEpsilon(Number(e.target.value))
                            }
                            inputProps={{ min: 0.01, step: 0.1 }}
                            helperText="Lower ε = stronger privacy guarantee"
                          />
                        </Box>
                        <Box
                          sx={{
                            flex: "1 1 30%",
                            minWidth: 180,
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                          }}
                        >
                          <Checkbox
                            checked={dpApplyNoise}
                            onChange={(_, checked) => setDpApplyNoise(checked)}
                          />
                          <Typography variant="body2">
                            Apply Laplace noise to enforce ε budget
                          </Typography>
                        </Box>
                      </Box>
                    )}
                  </>
                )}
              </Box>

              <Box
                sx={{ mt: 4, display: "flex", justifyContent: "space-between" }}
              >
                <Button
                  variant="outlined"
                  startIcon={<BackIcon />}
                  onClick={() => setActiveStep(0)}
                >
                  Back
                </Button>
                <Button
                  variant="contained"
                  size="large"
                  endIcon={<NextIcon />}
                  onClick={() => {
                    const configErr = validateConfig();
                    if (configErr) {
                      setFormError(configErr);
                      return;
                    }
                    setFormError("");
                    setActiveStep(2);
                  }}
                >
                  Next: Select Requirements
                </Button>
              </Box>
            </CardContent>
          </Card>
        )}

        {/* ── STEP 2: SELECT REQUIREMENTS ─────────────────────────── */}
        {activeStep === 2 && !isRunning && (
          <Card>
            <CardContent sx={{ p: 4 }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 700 }}>
                Link Requirements to Validation
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Select the ethical requirements you want to validate against.
                Thresholds will be automatically populated from the requirement
                specifications. You can also skip this step and run with manual
                thresholds.
              </Typography>

              {relevantRequirements.length === 0 ? (
                <Alert severity="info" sx={{ mb: 3 }}>
                  No requirements found for the selected validation types (
                  {selectedValidators.join(", ")}). You can still run the
                  validation with the thresholds configured in the previous
                  step.
                </Alert>
              ) : (
                <>
                  <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
                    <Button
                      size="small"
                      startIcon={<CheckBoxIcon />}
                      onClick={() =>
                        setSelectedRequirements(
                          relevantRequirements.map((r: any) => r.id),
                        )
                      }
                    >
                      Select All
                    </Button>
                    <Button
                      size="small"
                      startIcon={<CheckBoxBlankIcon />}
                      color="inherit"
                      onClick={() => setSelectedRequirements([])}
                    >
                      Clear
                    </Button>
                  </Box>

                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 1.5,
                      mb: 3,
                    }}
                  >
                    {relevantRequirements.map((req: any) => {
                      const isSelected = selectedRequirements.includes(req.id);
                      const principleColors: Record<
                        string,
                        { color: string; bg: string; border: string }
                      > = {
                        fairness: {
                          color: "#2e7d32",
                          bg: "#f1f8e9",
                          border: "#4caf50",
                        },
                        transparency: {
                          color: "#1565c0",
                          bg: "#e3f2fd",
                          border: "#2196f3",
                        },
                        privacy: {
                          color: "#e65100",
                          bg: "#fff3e0",
                          border: "#ff9800",
                        },
                        accountability: {
                          color: "#6a1b9a",
                          bg: "#f3e5f5",
                          border: "#9c27b0",
                        },
                      };
                      const colors =
                        principleColors[req.principle] ||
                        principleColors.fairness;
                      const rules = req.specification?.rules || [];
                      return (
                        <Card
                          key={req.id}
                          variant="outlined"
                          onClick={() => toggleRequirement(req.id)}
                          sx={{
                            cursor: "pointer",
                            borderColor: isSelected ? colors.border : "divider",
                            bgcolor: isSelected
                              ? colors.bg
                              : "background.paper",
                            transition: "all 0.2s",
                            "&:hover": { borderColor: colors.border },
                          }}
                        >
                          <CardContent sx={{ p: 2, "&:last-child": { pb: 2 } }}>
                            <Box
                              sx={{
                                display: "flex",
                                alignItems: "flex-start",
                                gap: 1.5,
                              }}
                            >
                              <Box
                                sx={{
                                  color: isSelected
                                    ? colors.color
                                    : "text.disabled",
                                  mt: 0.2,
                                }}
                              >
                                {isSelected ? (
                                  <CheckBoxIcon />
                                ) : (
                                  <CheckBoxBlankIcon />
                                )}
                              </Box>
                              <Box sx={{ flex: 1 }}>
                                <Box
                                  sx={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 1,
                                    mb: 0.5,
                                  }}
                                >
                                  <Typography
                                    variant="subtitle1"
                                    sx={{ fontWeight: 600 }}
                                  >
                                    {req.name}
                                  </Typography>
                                  <Chip
                                    label={req.principle}
                                    size="small"
                                    sx={{
                                      bgcolor: colors.bg,
                                      color: colors.color,
                                      border: `1px solid ${colors.border}`,
                                      fontWeight: 600,
                                      textTransform: "capitalize",
                                    }}
                                  />
                                  {req.elicited_automatically && (
                                    <Chip
                                      label="Auto-elicited"
                                      size="small"
                                      variant="outlined"
                                      color="info"
                                    />
                                  )}
                                </Box>
                                {req.description && (
                                  <Typography
                                    variant="body2"
                                    color="text.secondary"
                                    sx={{ mb: 1 }}
                                  >
                                    {req.description}
                                  </Typography>
                                )}
                                {rules.length > 0 && (
                                  <Box
                                    sx={{
                                      display: "flex",
                                      gap: 0.75,
                                      flexWrap: "wrap",
                                    }}
                                  >
                                    {rules.map((rule: any, i: number) => (
                                      <Chip
                                        key={i}
                                        label={`${(rule.metric || "").replace(/_/g, " ")} ${rule.operator} ${rule.value}`}
                                        size="small"
                                        variant="outlined"
                                        sx={{ fontSize: "0.75rem" }}
                                      />
                                    ))}
                                  </Box>
                                )}
                              </Box>
                            </Box>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </Box>

                  {selectedRequirements.length > 0 &&
                    !useRequirementThresholds && (
                      <Alert severity="info" sx={{ mb: 2 }}>
                        <Typography variant="body2">
                          <strong>{selectedRequirements.length}</strong>{" "}
                          requirement(s) selected. Click "Apply Thresholds" to
                          use the thresholds defined in these requirements
                          instead of the manually configured values.
                        </Typography>
                        <Button
                          size="small"
                          variant="outlined"
                          sx={{ mt: 1 }}
                          onClick={(e) => {
                            e.stopPropagation();
                            applyRequirementThresholds();
                          }}
                        >
                          Apply Thresholds from Requirements
                        </Button>
                      </Alert>
                    )}

                  {useRequirementThresholds && (
                    <Alert severity="success" sx={{ mb: 2 }}>
                      Thresholds have been applied from the selected
                      requirements.
                    </Alert>
                  )}
                </>
              )}

              <Box
                sx={{ mt: 3, display: "flex", justifyContent: "space-between" }}
              >
                <Button
                  variant="outlined"
                  startIcon={<BackIcon />}
                  onClick={() => setActiveStep(1)}
                >
                  Back
                </Button>
                <Box sx={{ display: "flex", gap: 2 }}>
                  {relevantRequirements.length > 0 &&
                    selectedRequirements.length === 0 && (
                      <Button variant="outlined" onClick={() => handleRun()}>
                        Skip – Use Manual Thresholds
                      </Button>
                    )}
                  <Button
                    variant="contained"
                    size="large"
                    startIcon={<RunIcon />}
                    onClick={() => handleRun()}
                  >
                    Run{" "}
                    {selectedValidators.length === VALIDATORS.length
                      ? "All"
                      : selectedValidators.length}{" "}
                    Validation{selectedValidators.length !== 1 ? "s" : ""}
                  </Button>
                </Box>
              </Box>
            </CardContent>
          </Card>
        )}

        {/* ── PROGRESS ──────────────────────────────────────────────── */}
        {isRunning && (
          <Paper sx={{ p: 4, mb: 3 }}>
            <Box sx={{ display: "flex", alignItems: "center", mb: 2, gap: 2 }}>
              <CircularProgress size={28} />
              <Typography variant="h6">Running Validations…</Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={progress}
              sx={{ mb: 1.5, height: 10, borderRadius: 1 }}
            />
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {currentStep} ({progress}%)
            </Typography>
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              {selectedValidators.map((key) => {
                const v = VALIDATORS.find((d) => d.key === key)!;
                return (
                  <Chip
                    key={key}
                    label={v.label}
                    size="small"
                    sx={{
                      bgcolor: v.bgColor,
                      color: v.color,
                      border: `1px solid ${v.borderColor}`,
                    }}
                  />
                );
              })}
            </Box>
          </Paper>
        )}

        {/* ── STEP 3: RESULTS ───────────────────────────────────────── */}
        {activeStep === 3 && results && (
          <Box>
            <Alert
              severity={results.overall_passed ? "success" : "warning"}
              sx={{ mb: 3 }}
              icon={results.overall_passed ? <CheckIcon /> : <FailIcon />}
            >
              <Typography variant="h6">
                Validation Suite{" "}
                {results.overall_passed ? "Passed ✓" : "Has Issues ⚠"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Suite ID: {results.suite_id}
              </Typography>
            </Alert>

            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
                gap: 3,
              }}
            >
              {/* Fairness */}
              {results.validations?.fairness && (
                <Card elevation={2} sx={{ border: "1px solid #4caf50" }}>
                  <CardContent>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        mb: 2,
                        gap: 1.5,
                      }}
                    >
                      <FairnessIcon sx={{ color: "#4caf50", fontSize: 32 }} />
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="h6" sx={{ fontWeight: 700 }}>
                          Fairness
                        </Typography>
                        <Chip
                          label={results.validations.fairness.status}
                          size="small"
                          color={
                            results.validations.fairness.status === "completed"
                              ? "success"
                              : "default"
                          }
                        />
                      </Box>
                    </Box>
                    {results.validations.fairness.results?.length > 0 && (
                      <Box>
                        <Typography variant="subtitle2" sx={{ mb: 1 }}>
                          Metrics
                        </Typography>
                        {results.validations.fairness.results.map(
                          (m: any, i: number) => (
                            <Box
                              key={i}
                              sx={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                mb: 0.75,
                              }}
                            >
                              <Typography variant="body2">
                                {m.metric_name.replace(/_/g, " ")}
                              </Typography>
                              <Box
                                sx={{
                                  display: "flex",
                                  gap: 1,
                                  alignItems: "center",
                                }}
                              >
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                >
                                  {m.metric_value?.toFixed(3)} / {m.threshold}
                                </Typography>
                                <Button
                                  size="small"
                                  variant="text"
                                  onClick={() => setSelectedFairnessMetric(m)}
                                  sx={{ minWidth: "auto", px: 1 }}
                                >
                                  Details
                                </Button>
                                <PassChip passed={m.passed} />
                              </Box>
                            </Box>
                          ),
                        )}
                      </Box>
                    )}
                    {results.validations.fairness.mlflow_run_id && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: "block", mt: 1.5 }}
                      >
                        MLflow:{" "}
                        {results.validations.fairness.mlflow_run_id.substring(
                          0,
                          8,
                        )}
                        …
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Transparency */}
              {results.validations?.transparency && (
                <Card elevation={2} sx={{ border: "1px solid #2196f3" }}>
                  <CardContent>
                    {results.validations.transparency.warning && (
                      <Alert severity="warning" sx={{ mb: 2 }}>
                        {results.validations.transparency.warning}. Upload a
                        properly trained model with varying predictions and
                        matching feature schema.
                      </Alert>
                    )}
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        mb: 2,
                        gap: 1.5,
                      }}
                    >
                      <TransparencyIcon
                        sx={{ color: "#2196f3", fontSize: 32 }}
                      />
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="h6" sx={{ fontWeight: 700 }}>
                          Transparency
                        </Typography>
                        <Chip
                          label={results.validations.transparency.status}
                          size="small"
                          color={
                            results.validations.transparency.status ===
                            "completed"
                              ? "success"
                              : "default"
                          }
                        />
                      </Box>
                    </Box>
                    {results.validations.transparency.global_importance && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" sx={{ mb: 1 }}>
                          Top Features
                        </Typography>
                        {Object.entries(
                          results.validations.transparency.global_importance,
                        )
                          .sort(([, a]: any, [, b]: any) => b - a)
                          .slice(0, 5)
                          .map(([feat, imp]: any) => (
                            <Box
                              key={feat}
                              sx={{
                                display: "flex",
                                justifyContent: "space-between",
                                mb: 0.5,
                              }}
                            >
                              <Typography variant="caption">{feat}</Typography>
                              <Typography
                                variant="caption"
                                sx={{ fontWeight: 700 }}
                              >
                                {(imp * 100).toFixed(1)}%
                              </Typography>
                            </Box>
                          ))}
                      </Box>
                    )}
                    {results.validations.transparency.model_card
                      ?.performance_metrics && (
                      <Box
                        sx={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: 0.75,
                          mb: 1.5,
                        }}
                      >
                        {Object.entries(
                          results.validations.transparency.model_card
                            .performance_metrics,
                        ).map(([k, val]: any) => (
                          <Chip
                            key={k}
                            label={`${k}: ${(val * 100).toFixed(1)}%`}
                            size="small"
                            variant="outlined"
                          />
                        ))}
                      </Box>
                    )}

                    {/* Explanation Fidelity */}
                    {results.validations.transparency.explanation_fidelity !=
                      null && (
                      <Box sx={{ mb: 1.5 }}>
                        <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                          Explanation Fidelity
                        </Typography>
                        <Box
                          sx={{ display: "flex", alignItems: "center", gap: 1 }}
                        >
                          <LinearProgress
                            variant="determinate"
                            value={
                              results.validations.transparency
                                .explanation_fidelity * 100
                            }
                            sx={{ flex: 1, height: 8, borderRadius: 1 }}
                            color={
                              results.validations.transparency
                                .explanation_fidelity >= 0.8
                                ? "success"
                                : results.validations.transparency
                                      .explanation_fidelity >= 0.5
                                  ? "warning"
                                  : "error"
                            }
                          />
                          <Typography
                            variant="caption"
                            sx={{
                              fontWeight: 700,
                              minWidth: 48,
                              textAlign: "right",
                            }}
                          >
                            {(
                              results.validations.transparency
                                .explanation_fidelity * 100
                            ).toFixed(1)}
                            %
                          </Typography>
                        </Box>
                        <Typography variant="caption" color="text.secondary">
                          1 − mean(|f(x) − g(x)|) — how faithfully LIME
                          approximates the model
                        </Typography>
                      </Box>
                    )}

                    {/* LIME Local Explanation (1 sample) */}
                    {results.validations.transparency.lime_explanations
                      ?.length > 0 &&
                      (() => {
                        const lime =
                          results.validations.transparency.lime_explanations[0];
                        const contributions = lime.feature_contributions
                          ? Object.entries(lime.feature_contributions)
                              .sort(
                                ([, a]: any, [, b]: any) =>
                                  Math.abs(b) - Math.abs(a),
                              )
                              .slice(0, 5)
                          : [];
                        const hasSignificant = contributions.some(
                          ([, w]: any) => Math.abs(w) > 1e-6,
                        );
                        return (
                          <Box sx={{ mb: 1.5 }}>
                            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                              LIME — Sample #{lime.sample_index}
                              {lime.predicted_label != null &&
                                ` → ${lime.predicted_label}`}
                              {lime.prediction_probability != null &&
                                ` (${(lime.prediction_probability * 100).toFixed(1)}%)`}
                            </Typography>
                            {hasSignificant ? (
                              <Box
                                sx={{
                                  p: 2,
                                  bgcolor: "black.05",
                                  borderRadius: 1,
                                  border: "1.5px solid black",
                                }}
                              >
                                {contributions.map(([feat, weight]: any) => (
                                  <Box
                                    key={feat}
                                    sx={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      mb: 0.25,
                                    }}
                                  >
                                    <Typography variant="caption">
                                      {feat}
                                    </Typography>
                                    <Typography
                                      variant="caption"
                                      sx={{
                                        fontWeight: 700,
                                        color:
                                          weight >= 0
                                            ? "success.main"
                                            : "error.main",
                                      }}
                                    >
                                      {weight >= 0 ? "+" : ""}
                                      {weight.toFixed(4)}
                                    </Typography>
                                  </Box>
                                ))}
                              </Box>
                            ) : (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                All contributions ≈ 0 — model predictions are
                                uniform across perturbations.
                              </Typography>
                            )}
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{ display: "block", mt: 0.5 }}
                            >
                              See Full Report for all{" "}
                              {
                                results.validations.transparency
                                  .lime_explanations.length
                              }{" "}
                              LIME explanations.
                            </Typography>
                          </Box>
                        );
                      })()}

                    {results.validations.transparency.mlflow_run_id && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: "block", mb: 1 }}
                      >
                        MLflow:{" "}
                        {results.validations.transparency.mlflow_run_id.substring(
                          0,
                          8,
                        )}
                        …
                      </Typography>
                    )}
                    <Button
                      variant="outlined"
                      size="small"
                      fullWidth
                      onClick={() =>
                        navigate(
                          `/validations/${results.suite_id}/transparency`,
                        )
                      }
                    >
                      Full Transparency Report
                    </Button>
                  </CardContent>
                </Card>
              )}

              {/* Privacy */}
              {results.validations?.privacy && (
                <Card elevation={2} sx={{ border: "1px solid #ff9800" }}>
                  <CardContent>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        mb: 2,
                        gap: 1.5,
                      }}
                    >
                      <PrivacyIcon sx={{ color: "#ff9800", fontSize: 32 }} />
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="h6" sx={{ fontWeight: 700 }}>
                          Privacy
                        </Typography>
                        <Chip
                          label={results.validations.privacy.status}
                          size="small"
                          color={
                            results.validations.privacy.status === "completed"
                              ? "success"
                              : "default"
                          }
                        />
                      </Box>
                      <PassChip
                        passed={results.validations.privacy.overall_passed}
                      />
                    </Box>
                    {results.validations.privacy.pii_detected != null && (
                      <Typography
                        variant="body2"
                        sx={{ mb: 1 }}
                        color={
                          results.validations.privacy.pii_detected.length > 0
                            ? "error"
                            : "success.main"
                        }
                      >
                        {results.validations.privacy.pii_detected.length > 0
                          ? `⚠️ ${results.validations.privacy.pii_detected.length} PII column(s) detected`
                          : "✓ No PII detected"}
                      </Typography>
                    )}
                    {results.validations.privacy.k_anonymity && (
                      <Box sx={{ mb: 1 }}>
                        <Typography variant="caption" sx={{ fontWeight: 600 }}>
                          k-Anonymity (k=
                          {results.validations.privacy.k_anonymity.k_value}
                          ):{" "}
                        </Typography>
                        <Chip
                          label={
                            results.validations.privacy.k_anonymity.satisfies_k
                              ? "PASSED"
                              : "FAILED"
                          }
                          color={
                            results.validations.privacy.k_anonymity.satisfies_k
                              ? "success"
                              : "error"
                          }
                          size="small"
                        />
                      </Box>
                    )}
                    {results.validations.privacy.l_diversity && (
                      <Box sx={{ mb: 1.5 }}>
                        <Typography variant="caption" sx={{ fontWeight: 600 }}>
                          l-Diversity (l=
                          {results.validations.privacy.l_diversity.l_value}
                          ):{" "}
                        </Typography>
                        <Chip
                          label={
                            results.validations.privacy.l_diversity.satisfies_l
                              ? "PASSED"
                              : "FAILED"
                          }
                          color={
                            results.validations.privacy.l_diversity.satisfies_l
                              ? "success"
                              : "error"
                          }
                          size="small"
                        />
                      </Box>
                    )}
                    {results.validations.privacy.mlflow_run_id && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: "block", mb: 1 }}
                      >
                        MLflow:{" "}
                        {results.validations.privacy.mlflow_run_id.substring(
                          0,
                          8,
                        )}
                        …
                      </Typography>
                    )}
                    <Button
                      variant="outlined"
                      size="small"
                      fullWidth
                      onClick={() =>
                        navigate(`/validations/${results.suite_id}/privacy`)
                      }
                    >
                      Full Privacy Report
                    </Button>
                  </CardContent>
                </Card>
              )}

              {/* Accountability */}
              {results.validations?.accountability && (
                <Card elevation={2} sx={{ border: "1px solid #9c27b0" }}>
                  <CardContent>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        mb: 2,
                        gap: 1.5,
                      }}
                    >
                      <AccountabilityIcon
                        sx={{ color: "#9c27b0", fontSize: 32 }}
                      />
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="h6" sx={{ fontWeight: 700 }}>
                          Accountability
                        </Typography>
                        <Chip
                          label="Audit Recorded"
                          color="success"
                          size="small"
                        />
                      </Box>
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {results.validations.accountability.message ||
                        "Audit trail recorded via MLflow."}
                    </Typography>
                    {results.validations.accountability.mlflow_run_id && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: "block", mt: 1 }}
                      >
                        MLflow Run:{" "}
                        {results.validations.accountability.mlflow_run_id.substring(
                          0,
                          8,
                        )}
                        …
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              )}
            </Box>

            <Box sx={{ mt: 4, display: "flex", gap: 2, flexWrap: "wrap" }}>
              <Button
                variant="outlined"
                onClick={() => navigate(`/projects/${id}`)}
              >
                Back to Project
              </Button>
              <Button
                variant="outlined"
                onClick={() => {
                  const activeSuiteId = results?.suite_id || suiteId;
                  if (activeSuiteId)
                    navigate(`/reports/validation/${activeSuiteId}`);
                }}
              >
                View Full Report
              </Button>
              <Button variant="outlined" onClick={handleDownloadSuitePdf}>
                Download PDF
              </Button>
              <Button
                variant="outlined"
                onClick={() => {
                  const blob = new Blob([JSON.stringify(results, null, 2)], {
                    type: "application/json",
                  });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `validation_results_${results?.suite_id || "export"}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                Export JSON
              </Button>
              <Button
                variant="outlined"
                color="secondary"
                startIcon={<RunIcon />}
                onClick={() => {
                  // Re-run: go back to step 0 keeping the current config
                  setResults(null);
                  setRunError("");
                  setIsRunning(false);
                  setTaskId("");
                  setSuiteId("");
                  setProgress(0);
                  setCurrentStep("");
                  setActiveStep(0);
                }}
              >
                Re-run Same Config
              </Button>
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={handleReset}
              >
                Run Another Validation
              </Button>
            </Box>
          </Box>
        )}

        <FairnessMetricDetail
          open={!!selectedFairnessMetric}
          onClose={() => setSelectedFairnessMetric(null)}
          metric={selectedFairnessMetric}
        />
      </Container>
    </>
  );
}
