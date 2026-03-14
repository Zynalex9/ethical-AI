/**
 * TraceabilityPage – Phase 3.4
 *
 * Full-page view for the Requirement Traceability Matrix.
 * Tabs: Full Matrix | By Requirement | By Dataset | By Model
 * Summary cards at top + root-cause analysis dialog.
 */

import { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
    Box,
    Container,
    Typography,
    Tabs,
    Tab,
    Card,
    CardContent,
    Grid,
    CircularProgress,
    Alert,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Chip,
    Divider,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Paper,
    Stack,
    LinearProgress,
} from '@mui/material';
import {
    CheckCircle as PassIcon,
    Cancel as FailIcon,
    BugReport as RootCauseIcon,
    Lightbulb as RecommendIcon,
    Timeline as HistoryIcon,
    AccountTree as TraceIcon,
    Assessment as MetricIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { traceabilityApi, requirementsApi, datasetsApi, modelsApi } from '../services/api';
import TraceabilityMatrix, { type TraceEntry, type TraceSummary } from '../components/TraceabilityMatrix';

/* ---------- Tab helper ---------- */
function TabPanel({ children, value, index }: { children?: React.ReactNode; value: number; index: number }) {
    return <div hidden={value !== index}>{value === index && <Box sx={{ pt: 3 }}>{children}</Box>}</div>;
}

/* ---------- Summary card ---------- */
function SummaryCard({ label, value, color }: { label: string; value: number | string; color: string }) {
    return (
        <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent sx={{ textAlign: 'center', py: 2 }}>
                <Typography variant="h4" fontWeight={700} color={color}>
                    {value}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {label}
                </Typography>
            </CardContent>
        </Card>
    );
}

/* ---------- Root-cause dialog ---------- */
function RootCauseDialog({
    open,
    onClose,
    validationId,
}: {
    open: boolean;
    onClose: () => void;
    validationId: string | null;
}) {
    const { data, isLoading } = useQuery({
        queryKey: ['root-cause', validationId],
        queryFn: () => traceabilityApi.getRootCause(validationId!),
        enabled: !!validationId && open,
    });

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <RootCauseIcon color="error" />
                    Root-Cause Analysis
                </Box>
            </DialogTitle>
            <DialogContent dividers>
                {isLoading ? (
                    <Box sx={{ textAlign: 'center', py: 4 }}>
                        <CircularProgress />
                    </Box>
                ) : data ? (
                    <Box>
                        {/* Overview */}
                        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                            <Chip
                                icon={data.overall_passed ? <PassIcon /> : <FailIcon />}
                                label={data.overall_passed ? 'Passed' : 'Failed'}
                                color={data.overall_passed ? 'success' : 'error'}
                            />
                            <Chip label={`${data.passed_metrics}/${data.total_metrics} metrics passed`} />
                        </Stack>

                        {/* Behavior pattern */}
                        {data.behavior_pattern && (
                            <Alert severity="info" sx={{ mb: 2 }}>
                                <Typography variant="subtitle2">Model Behavior</Typography>
                                <Typography variant="body2">{data.behavior_pattern}</Typography>
                            </Alert>
                        )}

                        {/* Linked requirement */}
                        {data.requirement && (
                            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                                <Typography variant="subtitle2" gutterBottom>
                                    Violated Requirement
                                </Typography>
                                <Typography variant="body2">
                                    <strong>{data.requirement.name}</strong> ({data.requirement.principle})
                                </Typography>
                                {data.requirement.description && (
                                    <Typography variant="body2" color="text.secondary">
                                        {data.requirement.description}
                                    </Typography>
                                )}
                            </Paper>
                        )}

                        {/* Root causes */}
                        <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                            Root Causes
                        </Typography>
                        <List dense>
                            {(data.root_causes ?? []).map((cause: any, i: number) => (
                                <ListItem key={i} sx={{ alignItems: 'flex-start' }}>
                                    <ListItemIcon sx={{ mt: 0.5 }}>
                                        <FailIcon color="error" fontSize="small" />
                                    </ListItemIcon>
                                    <ListItemText
                                        primary={
                                            <Box>
                                                <Chip
                                                    size="small"
                                                    label={cause.metric_name}
                                                    variant="outlined"
                                                    sx={{ mr: 1 }}
                                                />
                                                {cause.gap !== null && (
                                                    <Chip
                                                        size="small"
                                                        label={`Gap: ${cause.gap}`}
                                                        color="error"
                                                        variant="outlined"
                                                    />
                                                )}
                                            </Box>
                                        }
                                        secondary={cause.description}
                                    />
                                </ListItem>
                            ))}
                        </List>

                        <Divider sx={{ my: 2 }} />

                        {/* Recommendations */}
                        <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                            Recommendations
                        </Typography>
                        <List dense>
                            {(data.recommendations ?? []).map((rec: string, i: number) => (
                                <ListItem key={i}>
                                    <ListItemIcon>
                                        <RecommendIcon color="warning" fontSize="small" />
                                    </ListItemIcon>
                                    <ListItemText primary={rec} />
                                </ListItem>
                            ))}
                        </List>
                    </Box>
                ) : (
                    <Alert severity="warning">No data available.</Alert>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}

/* ---------- By-Requirement tab ---------- */
function ByRequirementTab({ projectId }: { projectId: string }) {
    const [selectedReq, setSelectedReq] = useState<string>('');

    const { data: requirements = [] } = useQuery({
        queryKey: ['requirements', projectId],
        queryFn: () => requirementsApi.listByProject(projectId),
    });

    const { data: history, isLoading } = useQuery({
        queryKey: ['req-history', selectedReq],
        queryFn: () => traceabilityApi.getRequirementHistory(selectedReq),
        enabled: !!selectedReq,
    });

    const passFailHistory = (history?.history || []).filter(
        (h: any) => h?.overall_passed === true || h?.overall_passed === false
    );

    return (
        <Box>
            <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel>Select Requirement</InputLabel>
                <Select
                    value={selectedReq}
                    label="Select Requirement"
                    onChange={(e) => setSelectedReq(e.target.value)}
                >
                    {requirements.map((r: any) => (
                        <MenuItem key={r.id} value={r.id}>
                            {r.name} ({r.principle})
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            {isLoading && <LinearProgress />}

            {history && passFailHistory.length > 0 ? (
                <Box>
                    <Typography variant="subtitle1" gutterBottom fontWeight={600}>
                        <HistoryIcon fontSize="small" sx={{ mr: 0.5, verticalAlign: 'middle' }} />
                        Compliance History — {history.requirement_name}
                    </Typography>
                    {passFailHistory.map((h: any) => (
                        <Paper key={h.validation_id} variant="outlined" sx={{ p: 2, mb: 1 }}>
                            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                                <Chip
                                    size="small"
                                    label={h.overall_passed ? 'Pass' : 'Fail'}
                                    color={h.overall_passed ? 'success' : 'error'}
                                />
                                <Typography variant="body2">
                                    Model: {h.model_name} | Dataset: {h.dataset_name}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                                    {h.completed_at ? new Date(h.completed_at).toLocaleString() : h.created_at ? new Date(h.created_at).toLocaleString() : ''}
                                </Typography>
                            </Stack>
                            {h.behavior_pattern && (
                                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                                    {h.behavior_pattern}
                                </Typography>
                            )}
                            <Stack direction="row" spacing={1} flexWrap="wrap">
                                {h.results?.map((r: any, ri: number) => (
                                    <Chip
                                        key={ri}
                                        size="small"
                                        variant="outlined"
                                        color={r.passed ? 'success' : 'error'}
                                        label={`${r.metric_name}: ${r.metric_value !== null ? r.metric_value.toFixed(3) : '—'}`}
                                    />
                                ))}
                            </Stack>
                        </Paper>
                    ))}
                </Box>
            ) : selectedReq && !isLoading ? (
                <Alert severity="info">No validation history for this requirement yet.</Alert>
            ) : null}
        </Box>
    );
}

/* ---------- By-Dataset tab ---------- */
function ByDatasetTab({ projectId }: { projectId: string }) {
    const [selectedDs, setSelectedDs] = useState<string>('');

    const { data: datasets = [] } = useQuery({
        queryKey: ['datasets', projectId],
        queryFn: () => datasetsApi.list(projectId),
    });

    const { data: impact, isLoading } = useQuery({
        queryKey: ['ds-impact', selectedDs],
        queryFn: () => traceabilityApi.getDatasetImpact(selectedDs),
        enabled: !!selectedDs,
    });

    return (
        <Box>
            <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel>Select Dataset</InputLabel>
                <Select
                    value={selectedDs}
                    label="Select Dataset"
                    onChange={(e) => setSelectedDs(e.target.value)}
                >
                    {datasets.map((d: any) => (
                        <MenuItem key={d.id} value={d.id}>
                            {d.name} ({d.row_count} rows)
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            {isLoading && <LinearProgress />}

            {impact ? (
                <Box>
                    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                        <Typography variant="subtitle2">Dataset: {impact.dataset?.name}</Typography>
                        <Typography variant="body2" color="text.secondary">
                            {impact.total_validations_using_dataset} total validations used this dataset
                        </Typography>
                    </Paper>

                    <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                        Requirements Impact
                    </Typography>
                    {impact.requirements_impact?.map((ri: any, idx: number) => (
                        <Paper key={idx} variant="outlined" sx={{ p: 2, mb: 1 }}>
                            <Stack direction="row" spacing={1} alignItems="center">
                                <Chip size="small" label={ri.requirement.principle} color="primary" />
                                <Typography variant="body2" fontWeight={600}>
                                    {ri.requirement.name}
                                </Typography>
                                <Chip size="small" variant="outlined" label={`${ri.validation_count} validations`} />
                            </Stack>
                            {ri.latest_validation && (
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                                    Latest: {ri.latest_validation.status}
                                    {ri.latest_validation.completed_at
                                        ? ` at ${new Date(ri.latest_validation.completed_at).toLocaleString()}`
                                        : ''}
                                </Typography>
                            )}
                        </Paper>
                    ))}
                </Box>
            ) : selectedDs && !isLoading ? (
                <Alert severity="info">No impact data for this dataset yet.</Alert>
            ) : null}
        </Box>
    );
}

/* ---------- By-Model tab ---------- */
function ByModelTab({ projectId }: { projectId: string }) {
    const [selectedModel, setSelectedModel] = useState<string>('');

    const { data: models = [] } = useQuery({
        queryKey: ['models', projectId],
        queryFn: () => modelsApi.list(projectId),
    });

    // We reuse the matrix endpoint and filter client-side by model
    const { data: matrixData, isLoading } = useQuery({
        queryKey: ['traceability-matrix', projectId],
        queryFn: () => traceabilityApi.getMatrix(projectId),
    });

    const filteredTraces = (matrixData?.traces ?? []).filter(
        (t: TraceEntry) => t.model?.id === selectedModel
    );

    return (
        <Box>
            <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel>Select Model</InputLabel>
                <Select
                    value={selectedModel}
                    label="Select Model"
                    onChange={(e) => setSelectedModel(e.target.value)}
                >
                    {models.map((m: any) => (
                        <MenuItem key={m.id} value={m.id}>
                            {m.name} ({m.model_type})
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            {isLoading && <LinearProgress />}

            {selectedModel && filteredTraces.length > 0 ? (
                <TraceabilityMatrix
                    traces={filteredTraces}
                    summary={matrixData?.summary ?? { total_requirements: 0, total_validations: 0, pass_count: 0, fail_count: 0, not_validated_count: 0, pass_rate: 0 }}
                />
            ) : selectedModel && !isLoading ? (
                <Alert severity="info">No validations found for this model.</Alert>
            ) : null}
        </Box>
    );
}

/* =================================================================
   Main Page
   ================================================================= */
export default function TraceabilityPage() {
    const { id: projectId } = useParams<{ id: string }>();
    const [tab, setTab] = useState(0);
    const [rootCauseDialogOpen, setRootCauseDialogOpen] = useState(false);
    const [rootCauseValidationId, setRootCauseValidationId] = useState<string | null>(null);

    const {
        data: matrixData,
        isLoading,
        error,
    } = useQuery({
        queryKey: ['traceability-matrix', projectId],
        queryFn: () => traceabilityApi.getMatrix(projectId!),
        enabled: !!projectId,
    });

    const traces: TraceEntry[] = matrixData?.traces ?? [];
    const summary: TraceSummary = matrixData?.summary ?? {
        total_requirements: 0,
        total_validations: 0,
        pass_count: 0,
        fail_count: 0,
        not_validated_count: 0,
        pass_rate: 0,
    };

    const handleViewRootCause = (validationId: string) => {
        setRootCauseValidationId(validationId);
        setRootCauseDialogOpen(true);
    };

    if (!projectId) {
        return <Alert severity="error">No project ID provided.</Alert>;
    }

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <TraceIcon color="primary" />
                    <Typography variant="h4" fontWeight={700}>
                        Requirement Traceability Matrix
                    </Typography>
                </Box>
                <Typography variant="body1" color="text.secondary">
                    End-to-end traceability from ethical requirements to datasets, models, and validation results.
                </Typography>
            </Box>

            {/* Summary cards */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid size={{ xs: 6, sm: 3 }}>
                    <SummaryCard label="Requirements Defined" value={summary.total_requirements} color="primary.main" />
                </Grid>
                <Grid size={{ xs: 6, sm: 3 }}>
                    <SummaryCard label="Validations Run" value={summary.total_validations} color="info.main" />
                </Grid>
                <Grid size={{ xs: 6, sm: 3 }}>
                    <SummaryCard label="Overall Pass Rate" value={`${summary.pass_rate}%`} color={summary.pass_rate >= 70 ? 'success.main' : 'error.main'} />
                </Grid>
                <Grid size={{ xs: 6, sm: 3 }}>
                    <SummaryCard label="Needing Attention" value={summary.fail_count + summary.not_validated_count} color="warning.main" />
                </Grid>
            </Grid>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    Failed to load traceability data: {(error as Error).message}
                </Alert>
            )}

            {/* Tabs */}
            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 0 }}>
                <Tab icon={<TraceIcon />} iconPosition="start" label="Full Matrix" />
                <Tab icon={<MetricIcon />} iconPosition="start" label="By Requirement" />
                <Tab label="By Dataset" />
                <Tab label="By Model" />
            </Tabs>

            <Divider />

            {/* Tab 0: Full Matrix */}
            <TabPanel value={tab} index={0}>
                <TraceabilityMatrix
                    traces={traces}
                    summary={summary}
                    loading={isLoading}
                    onViewRootCause={handleViewRootCause}
                />
            </TabPanel>

            {/* Tab 1: By Requirement */}
            <TabPanel value={tab} index={1}>
                <ByRequirementTab projectId={projectId} />
            </TabPanel>

            {/* Tab 2: By Dataset */}
            <TabPanel value={tab} index={2}>
                <ByDatasetTab projectId={projectId} />
            </TabPanel>

            {/* Tab 3: By Model */}
            <TabPanel value={tab} index={3}>
                <ByModelTab projectId={projectId} />
            </TabPanel>

            {/* Root-cause dialog */}
            <RootCauseDialog
                open={rootCauseDialogOpen}
                onClose={() => setRootCauseDialogOpen(false)}
                validationId={rootCauseValidationId}
            />
        </Container>
    );
}
