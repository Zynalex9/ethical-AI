// RequirementForm.tsx — create or edit a requirement

import { useState, useEffect } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Button,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Alert,
    Box,
    Typography,
    Divider,
    Chip,
    IconButton,
    Tooltip,
} from '@mui/material';
import {
    Add as AddIcon,
    Delete as DeleteIcon,
    Info as InfoIcon,
} from '@mui/icons-material';
import type { Requirement } from './RequirementCard';

// Default threshold rules per principle
const DEFAULT_RULES: Record<string, { metric: string; operator: string; value: number }[]> = {
    fairness: [
        { metric: 'demographic_parity_ratio', operator: '>=', value: 0.8 },
        { metric: 'equalized_odds_ratio',     operator: '>=', value: 0.8 },
        { metric: 'disparate_impact_ratio',   operator: '>=', value: 0.8 },
    ],
    transparency: [
        { metric: 'shap_explanation_coverage', operator: '>=', value: 1.0 },
        { metric: 'model_card_generated',      operator: '==', value: 1.0 },
    ],
    privacy: [
        { metric: 'k_anonymity_k',         operator: '>=', value: 5 },
        { metric: 'pii_columns_detected',  operator: '==', value: 0 },
    ],
    accountability: [
        { metric: 'audit_trail_exists', operator: '==', value: 1.0 },
        { metric: 'mlflow_run_logged',  operator: '==', value: 1.0 },
    ],
};

const SUPPORTED_METRICS: Record<string, string[]> = {
    fairness: [
        'demographic_parity_ratio',
        'demographic_parity_difference',
        'equalized_odds_ratio',
        'equalized_odds_difference',
        'equal_opportunity_difference',
        'disparate_impact_ratio',
    ],
    transparency: [
        'shap_explanation_coverage',
        'model_card_generated',
    ],
    privacy: [
        'pii_detection',
        'pii_columns_detected',
        'k_anonymity_k',
        'l_diversity_l',
    ],
    accountability: [
        'audit_trail_exists',
        'mlflow_run_logged',
    ],
};

interface Rule {
    metric: string;
    operator: string;
    value: number | string;
}

interface RequirementFormProps {
    open: boolean;
    onClose: () => void;
    /** If provided, form is in edit mode */
    initialValues?: Partial<Requirement>;
    onSubmit: (data: {
        name: string;
        principle: string;
        description: string;
        specification: { rules: Rule[] };
    }) => Promise<void>;
    title?: string;
}

export default function RequirementForm({
    open,
    onClose,
    initialValues,
    onSubmit,
    title,
}: RequirementFormProps) {
    const [name, setName]             = useState('');
    const [principle, setPrinciple]   = useState('fairness');
    const [description, setDescription] = useState('');
    const [rules, setRules]           = useState<Rule[]>(DEFAULT_RULES['fairness']);
    const [saving, setSaving]         = useState(false);
    const [error, setError]           = useState('');

    // Populate from initialValues when editing
    useEffect(() => {
        if (open) {
            setName(initialValues?.name ?? '');
            setPrinciple(initialValues?.principle ?? 'fairness');
            setDescription(initialValues?.description ?? '');
            const existing = initialValues?.specification?.rules;
            setPrinciple(initialValues?.principle ?? 'fairness');
            setRules(
                existing?.length
                    ? existing
                    : DEFAULT_RULES[initialValues?.principle ?? 'fairness'] ?? []
            );
            setError('');
        }
    }, [open, initialValues]);

    // Auto-fill default rules when principle changes (only for new requirements)
    const handlePrincipleChange = (value: string) => {
        setPrinciple(value);
        if (!initialValues?.id) {
            setRules(DEFAULT_RULES[value] ?? []);
        }
    };

    const handleRuleChange = (idx: number, field: keyof Rule, value: string) => {
        setRules((prev) => {
            const updated = [...prev];
            updated[idx] = {
                ...updated[idx],
                [field]: field === 'value' ? (isNaN(Number(value)) ? value : Number(value)) : value,
            };
            return updated;
        });
    };

    const addRule = () =>
        setRules((prev) => [
            ...prev,
            {
                metric: (SUPPORTED_METRICS[principle] ?? [])[0] ?? '',
                operator: '>=',
                value: 0,
            },
        ]);

    const removeRule = (idx: number) =>
        setRules((prev) => prev.filter((_, i) => i !== idx));

    const handleSubmit = async () => {
        if (!name.trim()) { setError('Name is required'); return; }
        setSaving(true);
        setError('');
        try {
            await onSubmit({
                name: name.trim(),
                principle,
                description: description.trim(),
                specification: { rules },
            });
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.detail ?? err.message ?? 'Save failed');
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle sx={{ fontWeight: 700 }}>
                {title ?? (initialValues?.id ? 'Edit Requirement' : 'Create Requirement')}
            </DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                <TextField
                    label="Requirement Name"
                    fullWidth
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    sx={{ mt: 1, mb: 2 }}
                />

                <FormControl fullWidth sx={{ mb: 2 }}>
                    <InputLabel>Ethical Principle</InputLabel>
                    <Select
                        value={principle}
                        label="Ethical Principle"
                        onChange={(e) => handlePrincipleChange(e.target.value)}
                    >
                        <MenuItem value="fairness">Fairness</MenuItem>
                        <MenuItem value="transparency">Transparency</MenuItem>
                        <MenuItem value="privacy">Privacy</MenuItem>
                        <MenuItem value="accountability">Accountability</MenuItem>
                    </Select>
                </FormControl>

                <TextField
                    label="Description"
                    fullWidth
                    multiline
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    sx={{ mb: 3 }}
                />

                {/* Threshold rules */}
                <Divider sx={{ mb: 2 }}>
                    <Chip label="Threshold Rules" size="small" />
                </Divider>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                    <Typography variant="body2" color="text.secondary">
                        Define the metrics and thresholds this requirement enforces.
                    </Typography>
                    <Tooltip title="Add custom rule">
                        <Button size="small" startIcon={<AddIcon />} onClick={addRule}>Add Rule</Button>
                    </Tooltip>
                </Box>

                {rules.map((rule, idx) => (
                    <Box key={idx} sx={{ display: 'flex', gap: 1, mb: 1.5, alignItems: 'center' }}>
                        <FormControl size="small" sx={{ flex: 3 }}>
                            <InputLabel>Metric</InputLabel>
                            <Select
                                value={rule.metric}
                                label="Metric"
                                onChange={(e) => handleRuleChange(idx, 'metric', e.target.value)}
                            >
                                {(SUPPORTED_METRICS[principle] ?? []).map((metric) => (
                                    <MenuItem key={metric} value={metric}>{metric}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <FormControl size="small" sx={{ flex: 1 }}>
                            <InputLabel>Op</InputLabel>
                            <Select
                                value={rule.operator}
                                label="Op"
                                onChange={(e) => handleRuleChange(idx, 'operator', e.target.value)}
                            >
                                {['>=', '<=', '>', '<', '=='].map((op) => (
                                    <MenuItem key={op} value={op}>{op}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <TextField
                            label="Value"
                            size="small"
                            type="number"
                            value={rule.value}
                            onChange={(e) => handleRuleChange(idx, 'value', e.target.value)}
                            sx={{ flex: 1.5 }}
                            inputProps={{ step: 0.01 }}
                        />
                        <IconButton size="small" color="error" onClick={() => removeRule(idx)}>
                            <DeleteIcon fontSize="small" />
                        </IconButton>
                    </Box>
                ))}

                {rules.length === 0 && (
                    <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, display: 'flex', gap: 1, alignItems: 'center' }}>
                        <InfoIcon fontSize="small" color="disabled" />
                        <Typography variant="body2" color="text.secondary">
                            No threshold rules defined. Validation will record metrics without pass/fail checks.
                        </Typography>
                    </Box>
                )}
            </DialogContent>
            <DialogActions sx={{ p: 2.5, pt: 0 }}>
                <Button onClick={onClose} disabled={saving}>Cancel</Button>
                <Button variant="contained" onClick={handleSubmit} disabled={saving}>
                    {saving ? 'Saving…' : (initialValues?.id ? 'Save Changes' : 'Create Requirement')}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
