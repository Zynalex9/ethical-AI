import {
    Box,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Button,
    Typography,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Paper,
} from '@mui/material';

interface FairnessMetricRow {
    metric_name: string;
    metric_value: number;
    threshold: number;
    passed: boolean;
    details?: {
        description?: string;
        by_group?: Record<string, number | { tpr?: number; fpr?: number }>;
    };
}

interface FairnessMetricDefinition {
    title: string;
    definition: string;
    thresholdText: string;
    failMeaning: string;
    remediation: string;
    higherIsBetter: boolean;
}

const METRIC_DEFINITIONS: Record<string, FairnessMetricDefinition> = {
    demographic_parity_ratio: {
        title: 'Demographic Parity Ratio',
        definition: 'Measures whether positive prediction rates are balanced across demographic groups.',
        thresholdText: '>= 0.80',
        failMeaning: 'One group receives proportionally fewer positive outcomes than another group.',
        remediation: 'Review sensitive-feature correlations and consider reweighing or post-processing equalization.',
        higherIsBetter: true,
    },
    equalized_odds_ratio: {
        title: 'Equalized Odds Ratio',
        definition: 'Compares parity of true positive and false positive rates across groups.',
        thresholdText: '>= 0.80',
        failMeaning: 'Model error behavior differs across groups, indicating unequal treatment.',
        remediation: 'Inspect class-conditional errors by group and apply fairness-aware threshold tuning.',
        higherIsBetter: true,
    },
    disparate_impact_ratio: {
        title: 'Disparate Impact Ratio',
        definition: 'Selection-rate ratio used for ECOA/EEOC four-fifths rule style checks.',
        thresholdText: '>= 0.80',
        failMeaning: 'Protected group selection rate is too low relative to another group.',
        remediation: 'Rebalance training data and evaluate decision thresholds for adverse impact reduction.',
        higherIsBetter: true,
    },
    equalized_odds_difference: {
        title: 'Equalized Odds Difference',
        definition: 'Absolute difference in true and false positive rates between groups.',
        thresholdText: '<= 0.10',
        failMeaning: 'Error rates differ too much between groups.',
        remediation: 'Analyze subgroup confusion matrices and tune model calibration for parity.',
        higherIsBetter: false,
    },
    equal_opportunity_difference: {
        title: 'Equal Opportunity Difference',
        definition: 'Absolute difference in true positive rate between groups for the positive class.',
        thresholdText: '<= 0.05',
        failMeaning: 'Qualified individuals in one group are approved less often than those in another group.',
        remediation: 'Revisit class balance, decision thresholds, and subgroup recall before re-validating.',
        higherIsBetter: false,
    },
    demographic_parity_difference: {
        title: 'Demographic Parity Difference',
        definition: 'Absolute difference in positive prediction rates between groups.',
        thresholdText: '<= 0.10',
        failMeaning: 'Selection rates are too far apart across groups.',
        remediation: 'Apply pre-processing balancing and retrain with fairness constraints.',
        higherIsBetter: false,
    },
};

const formatMetricName = (name: string) => name.replace(/_/g, ' ');

const formatByGroupValue = (value: number | { tpr?: number; fpr?: number }) => {
    if (typeof value === 'number') {
        return value.toFixed(4);
    }
    const tpr = value?.tpr != null ? `TPR: ${value.tpr.toFixed(4)}` : null;
    const fpr = value?.fpr != null ? `FPR: ${value.fpr.toFixed(4)}` : null;
    return [tpr, fpr].filter(Boolean).join(' | ') || 'N/A';
};

const thresholdComparisonText = (metric: FairnessMetricRow, def: FairnessMetricDefinition) => {
    const value = metric.metric_value ?? 0;
    const threshold = metric.threshold ?? 0;
    const comparator = def.higherIsBetter ? '>=' : '<=';
    return `${value.toFixed(3)} vs required ${comparator} ${threshold.toFixed(3)}`;
};

export default function FairnessMetricDetail({
    open,
    onClose,
    metric,
}: {
    open: boolean;
    onClose: () => void;
    metric: FairnessMetricRow | null;
}) {
    if (!metric) return null;

    const def = METRIC_DEFINITIONS[metric.metric_name] || {
        title: formatMetricName(metric.metric_name),
        definition: 'Fairness metric used to compare outcomes across demographic groups.',
        thresholdText: metric.threshold != null ? `${metric.threshold}` : 'N/A',
        failMeaning: 'The fairness requirement was not satisfied for this validation run.',
        remediation: 'Review by-group rates and retrain with fairness controls.',
        higherIsBetter: true,
    };

    const byGroup = metric.details?.by_group || {};
    const hasByGroup = Object.keys(byGroup).length > 0;

    const whyText = metric.passed
        ? `This metric passed: ${thresholdComparisonText(metric, def)}.`
        : metric.details?.description || `${def.failMeaning} (${thresholdComparisonText(metric, def)}).`;

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle>{def.title}</DialogTitle>
            <DialogContent dividers>
                <Box sx={{ display: 'grid', gap: 2 }}>
                    <Box>
                        <Typography variant="subtitle2" color="text.secondary">Definition</Typography>
                        <Typography variant="body2">{def.definition}</Typography>
                    </Box>

                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, alignItems: 'center' }}>
                        <Typography variant="body2"><strong>Your Value:</strong> {metric.metric_value?.toFixed(3)}</Typography>
                        <Typography variant="body2"><strong>Threshold:</strong> {def.thresholdText}</Typography>
                        <Chip label={metric.passed ? 'Pass' : 'Fail'} color={metric.passed ? 'success' : 'error'} size="small" />
                    </Box>

                    <Box>
                        <Typography variant="subtitle2" color="text.secondary">Why {metric.passed ? 'it passed' : 'it failed'}</Typography>
                        <Typography variant="body2">{whyText}</Typography>
                    </Box>

                    <Box>
                        <Typography variant="subtitle2" color="text.secondary">What to do</Typography>
                        <Typography variant="body2">{def.remediation}</Typography>
                    </Box>

                    <Box>
                        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>Per-group breakdown</Typography>
                        {hasByGroup ? (
                            <Paper variant="outlined">
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Group</TableCell>
                                            <TableCell>Value</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {Object.entries(byGroup).map(([group, value]) => (
                                            <TableRow key={group}>
                                                <TableCell>{group}</TableCell>
                                                <TableCell>{formatByGroupValue(value)}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </Paper>
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                                No by-group breakdown is available for this metric in the current result.
                            </Typography>
                        )}
                    </Box>
                </Box>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}
