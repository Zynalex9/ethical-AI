import { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import type {
  CustomRule,
  CustomRuleCreateInput,
  SupportedCustomRuleOptions,
} from "../services/api";

interface CustomRuleEditorProps {
  projectId: string;
  rules: CustomRule[];
  selectedRuleIds: string[];
  options?: SupportedCustomRuleOptions;
  loadingOptions?: boolean;
  disabled?: boolean;
  onToggleRule: (ruleId: string) => void;
  onSaveRule: (payload: CustomRuleCreateInput) => Promise<void>;
}

interface FormState {
  name: string;
  description: string;
  base_metric: string;
  aggregation: "min_ratio" | "max_difference";
  comparison: ">=" | "<=";
  default_threshold: number;
}

const DEFAULT_FORM: FormState = {
  name: "",
  description: "",
  base_metric: "precision_score",
  aggregation: "min_ratio",
  comparison: ">=",
  default_threshold: 0.8,
};

export default function CustomRuleEditor({
  projectId,
  rules,
  selectedRuleIds,
  options,
  loadingOptions = false,
  disabled = false,
  onToggleRule,
  onSaveRule,
}: CustomRuleEditorProps) {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const baseMetricOptions = useMemo(() => {
    if (options?.base_metrics?.length) return options.base_metrics;
    return [
      "precision_score",
      "recall_score",
      "f1_score",
      "accuracy_score",
      "selection_rate",
      "true_positive_rate",
      "false_positive_rate",
    ];
  }, [options]);

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const validate = (): string => {
    if (!projectId) return "Project id is required before saving a custom rule.";
    if (!form.name.trim()) return "Rule name is required.";
    if (!form.base_metric) return "Base metric is required.";
    if (!Number.isFinite(form.default_threshold)) return "Threshold must be a finite number.";
    return "";
  };

  const handleSave = async () => {
    const message = validate();
    if (message) {
      setError(message);
      setSuccess("");
      return;
    }

    setIsSaving(true);
    setError("");
    setSuccess("");
    try {
      await onSaveRule({
        project_id: projectId,
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        principle: "fairness",
        base_metric: form.base_metric,
        aggregation: form.aggregation,
        comparison: form.comparison,
        default_threshold: Number(form.default_threshold),
      });
      setForm((prev) => ({
        ...DEFAULT_FORM,
        base_metric: prev.base_metric,
      }));
      setSuccess("Custom rule saved.");
    } catch (e: any) {
      setError(e?.message || "Failed to save custom rule.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
        Custom Rules
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Create reusable fairness rules and toggle which ones run in this validation.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 1.5 }} onClose={() => setError("")}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 1.5 }} onClose={() => setSuccess("")}>
          {success}
        </Alert>
      )}

      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} sx={{ mb: 1.5 }}>
        <TextField
          label="Rule name"
          size="small"
          value={form.name}
          onChange={(e) => setField("name", e.target.value)}
          disabled={disabled || isSaving}
          fullWidth
        />
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Base metric</InputLabel>
          <Select
            label="Base metric"
            value={form.base_metric}
            onChange={(e) => setField("base_metric", e.target.value)}
            disabled={disabled || isSaving || loadingOptions}
          >
            {baseMetricOptions.map((metric) => (
              <MenuItem key={metric} value={metric}>
                {metric}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>

      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} sx={{ mb: 1.5 }}>
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Aggregation</InputLabel>
          <Select
            label="Aggregation"
            value={form.aggregation}
            onChange={(e) => setField("aggregation", e.target.value as "min_ratio" | "max_difference")}
            disabled={disabled || isSaving}
          >
            <MenuItem value="min_ratio">min_ratio</MenuItem>
            <MenuItem value="max_difference">max_difference</MenuItem>
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Comparison</InputLabel>
          <Select
            label="Comparison"
            value={form.comparison}
            onChange={(e) => setField("comparison", e.target.value as ">=" | "<=")}
            disabled={disabled || isSaving}
          >
            <MenuItem value=">=">&gt;=</MenuItem>
            <MenuItem value="<=">&lt;=</MenuItem>
          </Select>
        </FormControl>

        <TextField
          label="Threshold"
          type="number"
          size="small"
          value={form.default_threshold}
          onChange={(e) => setField("default_threshold", Number(e.target.value))}
          inputProps={{ step: 0.01 }}
          disabled={disabled || isSaving}
          sx={{ minWidth: 140 }}
        />
      </Stack>

      <TextField
        label="Description (optional)"
        size="small"
        value={form.description}
        onChange={(e) => setField("description", e.target.value)}
        disabled={disabled || isSaving}
        fullWidth
        sx={{ mb: 1.5 }}
      />

      <Button
        variant="outlined"
        onClick={handleSave}
        disabled={disabled || isSaving || loadingOptions}
        sx={{ mb: 2 }}
      >
        {isSaving ? "Saving..." : "Save Rule"}
      </Button>

      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
        Toggle rules for this run:
      </Typography>
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
        {rules.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            No custom fairness rules yet.
          </Typography>
        )}
        {rules.map((rule) => {
          const selected = selectedRuleIds.includes(rule.id);
          return (
            <Chip
              key={rule.id}
              clickable
              color={selected ? "primary" : "default"}
              variant={selected ? "filled" : "outlined"}
              label={`${rule.name} (${rule.comparison} ${rule.default_threshold})`}
              onClick={() => onToggleRule(rule.id)}
            />
          );
        })}
      </Box>
    </Box>
  );
}
