// TemplateCustomizer – Phase 5 (6.4)
// Lets the user adjust rule thresholds, add / remove rules, then apply to a project.

import { useState, useEffect } from 'react';
import {
    Box,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Divider,
    FormControl,
    Grid,
    IconButton,
    InputLabel,
    MenuItem,
    Select,
    Slider,
    TextField,
    Typography,
    Chip,
    CircularProgress,
    Alert,
} from '@mui/material';
import {
    Add as AddIcon,
    Delete as DeleteIcon,
    RestartAlt as ResetIcon,
} from '@mui/icons-material';
import type { Template, TemplateRuleItem, Project } from '../types';

interface RuleState extends TemplateRuleItem {
    /** Keep track of original value for comparison */
    _originalValue: number;
}

interface TemplateCustomizerProps {
    open: boolean;
    template: Template;
    projects: Project[];
    loading?: boolean;
    onClose: () => void;
    /** Called with (projectId, customizations) when the user clicks Apply */
    onApply: (projectId: string, customizations: Record<string, any>) => void;
}

const OPERATORS = ['>=', '<=', '==', '>', '<'];

const PRINCIPLE_OPTIONS = ['fairness', 'transparency', 'privacy', 'accountability'];

export default function TemplateCustomizer({
    open,
    template,
    projects,
    loading = false,
    onClose,
    onApply,
}: TemplateCustomizerProps) {
    const [rules, setRules] = useState<RuleState[]>([]);
    const [selectedProjectId, setSelectedProjectId] = useState('');
    const [error, setError] = useState('');

    // Initialise rules from template
    useEffect(() => {
        const items: TemplateRuleItem[] = template.rules?.items || [];
        setRules(
            items.map((item) => ({
                ...item,
                _originalValue: item.value,
            })),
        );
        setSelectedProjectId('');
        setError('');
    }, [template]);

    // ── Handlers ────────────────────────────────────────────────────
    const updateRule = (index: number, field: keyof TemplateRuleItem, value: any) => {
        setRules((prev) => {
            const copy = [...prev];
            copy[index] = { ...copy[index], [field]: value };
            return copy;
        });
    };

    const removeRule = (index: number) => {
        setRules((prev) => prev.filter((_, i) => i !== index));
    };

    const addRule = () => {
        setRules((prev) => [
            ...prev,
            {
                metric: '',
                operator: '>=',
                value: 0.8,
                principle: 'fairness',
                description: '',
                _originalValue: 0.8,
            },
        ]);
    };

    const resetToDefaults = () => {
        const items: TemplateRuleItem[] = template.rules?.items || [];
        setRules(items.map((item) => ({ ...item, _originalValue: item.value })));
    };

    const handleApply = () => {
        if (!selectedProjectId) {
            setError('Please select a project');
            return;
        }

        // Build customizations payload
        const originalItems: TemplateRuleItem[] = template.rules?.items || [];
        const ruleOverrides: Record<string, any>[] = [];
        const addRules: Record<string, any>[] = [];
        const removeIndices: number[] = [];

        // Detect removed original rules (compare by tracking original index)
        const keptOriginalIndices = new Set<number>();

        for (const rule of rules) {
            // If the rule existed originally, check if it changed
            const matchIdx = originalItems.findIndex(
                (o, i) =>
                    !keptOriginalIndices.has(i) &&
                    o.metric === rule.metric &&
                    o.value === rule._originalValue,
            );
            if (matchIdx >= 0) {
                keptOriginalIndices.add(matchIdx);
                if (
                    rule.value !== originalItems[matchIdx].value ||
                    rule.operator !== originalItems[matchIdx].operator
                ) {
                    ruleOverrides.push({
                        index: matchIdx,
                        value: rule.value,
                        operator: rule.operator,
                        description: rule.description,
                    });
                }
            } else {
                // New rule added by user
                addRules.push({
                    metric: rule.metric,
                    operator: rule.operator,
                    value: rule.value,
                    principle: rule.principle || 'fairness',
                    description: rule.description,
                });
            }
        }

        // Determine which indices were removed
        for (let i = 0; i < originalItems.length; i++) {
            if (!keptOriginalIndices.has(i)) {
                removeIndices.push(i);
            }
        }

        const customizations: Record<string, any> = {};
        if (ruleOverrides.length) customizations.rule_overrides = ruleOverrides;
        if (addRules.length) customizations.add_rules = addRules;
        if (removeIndices.length) customizations.remove_indices = removeIndices;

        onApply(selectedProjectId, Object.keys(customizations).length > 0 ? customizations : undefined as any);
    };

    // ── Slider range helpers ────────────────────────────────────────
    const sliderMin = (op: string) => (op === '<=' || op === '<' ? 0 : 0);
    const sliderMax = (_op: string) => 1;
    const sliderStep = 0.01;

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>
                Customize Template: {template.name}
            </DialogTitle>

            <DialogContent dividers>
                {error && (
                    <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                        {error}
                    </Alert>
                )}

                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Adjust thresholds, add new rules, or remove rules before applying to your project.
                </Typography>

                {/* Rules list */}
                {rules.map((rule, idx) => {
                    const changed = rule.value !== rule._originalValue;
                    return (
                        <Box
                            key={idx}
                            sx={{
                                p: 2,
                                mb: 2,
                                border: '1px solid',
                                borderColor: changed ? 'primary.main' : 'divider',
                                borderRadius: 2,
                                bgcolor: changed ? 'rgba(102,126,234,0.04)' : 'transparent',
                            }}
                        >
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                <Typography variant="subtitle2">
                                    Rule {idx + 1}
                                    {changed && (
                                        <Chip label="Modified" size="small" color="primary" sx={{ ml: 1 }} />
                                    )}
                                </Typography>
                                <IconButton size="small" color="error" onClick={() => removeRule(idx)}>
                                    <DeleteIcon fontSize="small" />
                                </IconButton>
                            </Box>

                            <Grid container spacing={2} alignItems="center">
                                <Grid size={{ xs: 12, sm: 4 }}>
                                    <TextField
                                        label="Metric"
                                        size="small"
                                        fullWidth
                                        value={rule.metric}
                                        onChange={(e) => updateRule(idx, 'metric', e.target.value)}
                                    />
                                </Grid>
                                <Grid size={{ xs: 6, sm: 2 }}>
                                    <FormControl fullWidth size="small">
                                        <InputLabel>Op</InputLabel>
                                        <Select
                                            value={rule.operator}
                                            label="Op"
                                            onChange={(e) => updateRule(idx, 'operator', e.target.value)}
                                        >
                                            {OPERATORS.map((op) => (
                                                <MenuItem key={op} value={op}>{op}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid size={{ xs: 6, sm: 3 }}>
                                    <TextField
                                        label="Threshold"
                                        size="small"
                                        type="number"
                                        fullWidth
                                        value={rule.value}
                                        onChange={(e) => updateRule(idx, 'value', parseFloat(e.target.value) || 0)}
                                        inputProps={{ step: 0.01 }}
                                    />
                                </Grid>
                                <Grid size={{ xs: 12, sm: 3 }}>
                                    <FormControl fullWidth size="small">
                                        <InputLabel>Principle</InputLabel>
                                        <Select
                                            value={rule.principle || 'fairness'}
                                            label="Principle"
                                            onChange={(e) => updateRule(idx, 'principle', e.target.value)}
                                        >
                                            {PRINCIPLE_OPTIONS.map((p) => (
                                                <MenuItem key={p} value={p} sx={{ textTransform: 'capitalize' }}>{p}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                            </Grid>

                            {/* Slider for quick threshold adjustment */}
                            {rule.value <= 1 && rule.value >= 0 && (
                                <Box sx={{ px: 1, mt: 1 }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <Typography variant="caption" color="text.secondary">
                                            Original: {rule._originalValue}
                                        </Typography>
                                        <Typography variant="caption" color="primary">
                                            Current: {rule.value}
                                        </Typography>
                                    </Box>
                                    <Slider
                                        value={rule.value}
                                        min={sliderMin(rule.operator)}
                                        max={sliderMax(rule.operator)}
                                        step={sliderStep}
                                        onChange={(_e, val) => updateRule(idx, 'value', val as number)}
                                        size="small"
                                    />
                                </Box>
                            )}

                            <TextField
                                label="Description"
                                size="small"
                                fullWidth
                                value={rule.description || ''}
                                onChange={(e) => updateRule(idx, 'description', e.target.value)}
                                sx={{ mt: 1 }}
                            />
                        </Box>
                    );
                })}

                <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
                    <Button size="small" variant="outlined" startIcon={<AddIcon />} onClick={addRule}>
                        Add Rule
                    </Button>
                    <Button size="small" variant="text" startIcon={<ResetIcon />} onClick={resetToDefaults}>
                        Reset to Default
                    </Button>
                </Box>

                <Divider sx={{ mb: 2 }} />

                {/* Project selection */}
                <FormControl fullWidth>
                    <InputLabel>Apply to Project</InputLabel>
                    <Select
                        value={selectedProjectId}
                        label="Apply to Project"
                        onChange={(e) => setSelectedProjectId(e.target.value)}
                    >
                        {projects.map((p) => (
                            <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button
                    variant="contained"
                    disabled={loading || !selectedProjectId}
                    onClick={handleApply}
                >
                    {loading ? <CircularProgress size={20} /> : 'Apply Customized Template'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
