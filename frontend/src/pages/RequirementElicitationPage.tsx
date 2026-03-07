// RequirementElicitationPage.tsx — Cognitive RE: auto-generate ethical requirements

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    Box,
    Typography,
    Button,
    Grid,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Divider,
    Chip,
    Alert,
    AlertTitle,
    Collapse,
    Skeleton,
    Paper,
    Table,
    TableHead,
    TableRow,
    TableCell,
    TableBody,
    IconButton,
    Tooltip,
    Breadcrumbs,
    Link,
} from '@mui/material';
import {
    AutoFixHigh as ElicitIcon,
    TableChart as DatasetIcon,
    ModelTraining as ModelIcon,
    Add as AddIcon,
    Edit as EditIcon,
    Delete as DeleteIcon,
    CheckCircle as AcceptedIcon,
    NavigateNext as NavNextIcon,
} from '@mui/icons-material';
import { datasetsApi, modelsApi, requirementsApi } from '../services/api';
import RequirementCard, { type Requirement } from '../components/requirements/RequirementCard';
import RequirementForm from '../components/requirements/RequirementForm';

// ─── helpers ────────────────────────────────────────────────────────────────

interface Suggestion extends Requirement {
    isSuggestion: true;
}

const principleColor: Record<string, string> = {
    fairness:       '#2e7d32',
    transparency:   '#1565c0',
    privacy:        '#e65100',
    accountability: '#6a1b9a',
};

// ─── page ───────────────────────────────────────────────────────────────────

export default function RequirementElicitationPage() {
    const { id: projectId } = useParams<{ id: string }>();
    const navigate          = useNavigate();
    const queryClient       = useQueryClient();

    // Elicitation explanation banner
    const [showExplainer, setShowExplainer] = useState(true);

    // Analysis selections
    const [selectedDataset,  setSelectedDataset]  = useState('');
    const [selectedModel,    setSelectedModel]    = useState('');
    const [modelDataset,     setModelDataset]     = useState('');

    // Suggestions from elicitor
    const [datasetSuggestions, setDatasetSuggestions] = useState<Suggestion[]>([]);
    const [modelSuggestions,   setModelSuggestions]   = useState<Suggestion[]>([]);
    const [dismissedIds,       setDismissedIds]        = useState<Set<string>>(new Set());

    // Elicitation loading
    const [analyzingDataset, setAnalyzingDataset]  = useState(false);
    const [analyzingModel,   setAnalyzingModel]    = useState(false);
    const [elicitError,      setElicitError]       = useState('');

    // Manual form
    const [formOpen,    setFormOpen]    = useState(false);
    const [editTarget,  setEditTarget]  = useState<Requirement | null>(null);

    // ── queries ──────────────────────────────────────────────────────────────

    const { data: datasets = [] } = useQuery({
        queryKey: ['datasets', projectId],
        queryFn: () => datasetsApi.list(projectId!),
        enabled: !!projectId,
    });

    const { data: models = [] } = useQuery({
        queryKey: ['models', projectId],
        queryFn: () => modelsApi.list(projectId!),
        enabled: !!projectId,
    });

    const { data: savedRequirements = [], isLoading: loadingSaved } = useQuery({
        queryKey: ['requirements', projectId],
        queryFn: () => requirementsApi.listByProject(projectId!),
        enabled: !!projectId,
    });

    // ── mutations ─────────────────────────────────────────────────────────────

    const acceptMutation = useMutation({
        mutationFn: (suggestion: Suggestion) =>
            requirementsApi.acceptElicited({ ...suggestion, project_id: projectId! }),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['requirements', projectId] }),
    });

    const createMutation = useMutation({
        mutationFn: (data: any) => requirementsApi.create(projectId!, data),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['requirements', projectId] }),
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }: { id: string; data: any }) =>
            requirementsApi.update(id, data),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['requirements', projectId] }),
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => requirementsApi.delete(id),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['requirements', projectId] }),
    });

    // ── elicitation handlers ──────────────────────────────────────────────────

    const handleAnalyzeDataset = async () => {
        if (!selectedDataset) return;
        setAnalyzingDataset(true);
        setElicitError('');
        try {
            const res = await requirementsApi.elicitFromDataset({
                dataset_id: selectedDataset,
                project_id: projectId!,
            });
            setDatasetSuggestions(res.map((s: any) => ({ ...s, isSuggestion: true })));
        } catch (err: any) {
            setElicitError(err.response?.data?.detail ?? 'Dataset analysis failed');
        } finally {
            setAnalyzingDataset(false);
        }
    };

    const handleAnalyzeModel = async () => {
        if (!selectedModel || !modelDataset) return;
        setAnalyzingModel(true);
        setElicitError('');
        try {
            const res = await requirementsApi.elicitFromModel({
                model_id:   selectedModel,
                dataset_id: modelDataset,
                project_id: projectId!,
            });
            setModelSuggestions(res.map((s: any) => ({ ...s, isSuggestion: true })));
        } catch (err: any) {
            setElicitError(err.response?.data?.detail ?? 'Model analysis failed');
        } finally {
            setAnalyzingModel(false);
        }
    };

    const handleAccept = async (req: Requirement) => {
        await acceptMutation.mutateAsync(req as Suggestion);
        setDismissedIds((prev) => new Set(prev).add(req.name));
    };

    const handleReject = (req: Requirement) =>
        setDismissedIds((prev) => new Set(prev).add(req.name));

    // ── form save ─────────────────────────────────────────────────────────────

    const handleFormSubmit = async (data: any) => {
        if (editTarget?.id) {
            await updateMutation.mutateAsync({ id: editTarget.id!, data });
        } else {
            await createMutation.mutateAsync(data);
        }
    };

    // ── visible suggestions ───────────────────────────────────────────────────

    const allSuggestions = [...datasetSuggestions, ...modelSuggestions].filter(
        (s) => !dismissedIds.has(s.name)
    );

    // ─── render ───────────────────────────────────────────────────────────────

    return (
        <Box sx={{ p: 3 }}>
            {/* Breadcrumbs */}
            <Breadcrumbs separator={<NavNextIcon fontSize="small" />} sx={{ mb: 2 }}>
                <Link
                    component="button"
                    underline="hover"
                    color="inherit"
                    onClick={() => navigate(`/projects/${projectId}`)}
                    sx={{ cursor: 'pointer' }}
                >
                    Project
                </Link>
                <Typography color="text.primary">Requirement Elicitation</Typography>
            </Breadcrumbs>

            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
                <ElicitIcon color="primary" sx={{ fontSize: 32 }} />
                <Box>
                    <Typography variant="h5" fontWeight={700}>
                        Requirement Elicitation
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Cognitive RE — automatically discover ethical requirements from your dataset and model behaviour
                    </Typography>
                </Box>
            </Box>

            {elicitError && (
                <Alert severity="error" onClose={() => setElicitError('')} sx={{ mb: 2 }}>
                    {elicitError}
                </Alert>
            )}

            {/* ── What is elicitation? banner ─────────────────────────────── */}
            <Collapse in={showExplainer}>
                <Alert
                    severity="info"
                    sx={{ mb: 3 }}
                    onClose={() => setShowExplainer(false)}
                >
                    <AlertTitle sx={{ fontWeight: 700 }}>What is Requirement Elicitation?</AlertTitle>
                    <Typography variant="body2" sx={{ mb: 1 }}>
                        <strong>Elicitation</strong> is the <em>discovery phase</em>. This page scans your dataset
                        (column names, class distributions, PII patterns) and your model&apos;s predictions to
                        automatically <strong>suggest</strong> ethical requirements — for example:
                        &ldquo;Demographic parity ratio should be ≥ 0.8&rdquo; or &ldquo;No direct PII columns&rdquo;.
                        You can review each suggestion and save the ones that apply to your project.
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 1 }}>
                        <strong>Elicitation ≠ Validation.</strong> Elicitation only <em>identifies</em> what to
                        check — it does not run any metric calculations. Head to the{' '}
                        <strong>Validation</strong> page to <em>test</em> whether your model actually satisfies
                        the saved requirements.
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 0.5 }}>
                        <Chip label="1. Analyse dataset / model here" size="small" color="info" variant="outlined" />
                        <Chip label="2. Review &amp; save requirements" size="small" color="info" variant="outlined" />
                        <Chip label="3. Test them on the Validation page" size="small" color="info" variant="outlined" />
                    </Box>
                </Alert>
            </Collapse>

            <Grid container spacing={3} sx={{ mt: 0 }} columns={{ xs: 12, md: 12 }}>
                {/* ── Dataset Analysis ─────────────────────────────────────── */}
                <Grid size={{ xs: 12, md: 6 }}>
                    <Paper variant="outlined" sx={{ p: 2.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                            <DatasetIcon color="action" />
                            <Typography variant="h6" fontWeight={600}>Dataset Analysis</Typography>
                        </Box>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            Analyse column names, class distributions, and PII markers to surface requirements.
                        </Typography>
                        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
                            <InputLabel>Dataset</InputLabel>
                            <Select
                                value={selectedDataset}
                                label="Dataset"
                                onChange={(e) => setSelectedDataset(e.target.value)}
                            >
                                {datasets.map((d: any) => (
                                    <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <Button
                            variant="contained"
                            fullWidth
                            startIcon={<ElicitIcon />}
                            disabled={!selectedDataset || analyzingDataset}
                            onClick={handleAnalyzeDataset}
                        >
                            {analyzingDataset ? 'Analysing…' : 'Analyse Dataset'}
                        </Button>
                        {datasetSuggestions.length > 0 && (
                            <Chip
                                label={`${datasetSuggestions.length} suggestions`}
                                size="small"
                                color="success"
                                sx={{ mt: 1.5 }}
                            />
                        )}
                    </Paper>
                </Grid>

                {/* ── Model Behaviour Analysis ──────────────────────────────── */}
                <Grid size={{ xs: 12, md: 6 }}>
                    <Paper variant="outlined" sx={{ p: 2.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                            <ModelIcon color="action" />
                            <Typography variant="h6" fontWeight={600}>Model Behaviour Analysis</Typography>
                        </Box>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            Run predictions to detect disparate impact, prediction imbalance, and feature risks.
                        </Typography>
                        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
                            <InputLabel>Model</InputLabel>
                            <Select
                                value={selectedModel}
                                label="Model"
                                onChange={(e) => setSelectedModel(e.target.value)}
                            >
                                {models.map((m: any) => (
                                    <MenuItem key={m.id} value={m.id}>{m.name}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
                            <InputLabel>Dataset for inference</InputLabel>
                            <Select
                                value={modelDataset}
                                label="Dataset for inference"
                                onChange={(e) => setModelDataset(e.target.value)}
                            >
                                {datasets.map((d: any) => (
                                    <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <Button
                            variant="contained"
                            fullWidth
                            startIcon={<ElicitIcon />}
                            disabled={!selectedModel || !modelDataset || analyzingModel}
                            onClick={handleAnalyzeModel}
                        >
                            {analyzingModel ? 'Analysing…' : 'Analyse Model Behaviour'}
                        </Button>
                        {modelSuggestions.length > 0 && (
                            <Chip
                                label={`${modelSuggestions.length} suggestions`}
                                size="small"
                                color="success"
                                sx={{ mt: 1.5 }}
                            />
                        )}
                    </Paper>
                </Grid>
            </Grid>

            {/* ── Suggestions Section ──────────────────────────────────────── */}
            {allSuggestions.length > 0 && (
                <Box sx={{ mt: 4 }}>
                    <Divider sx={{ mb: 3 }}>
                        <Chip
                            icon={<ElicitIcon />}
                            label={`${allSuggestions.length} Generated Suggestion${allSuggestions.length !== 1 ? 's' : ''}`}
                            color="primary"
                        />
                    </Divider>
                    <Grid container spacing={2}>
                        {allSuggestions.map((suggestion, idx) => (
                            <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={`${suggestion.name}-${idx}`}>
                                <RequirementCard
                                    requirement={suggestion}
                                    isSuggestion
                                    onAccept={handleAccept}
                                    onReject={handleReject}
                                />
                            </Grid>
                        ))}
                    </Grid>
                </Box>
            )}

            {/* ── Saved Requirements Section ───────────────────────────────── */}
            <Box sx={{ mt: 4 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <AcceptedIcon color="success" />
                        <Typography variant="h6" fontWeight={600}>
                            Accepted Requirements
                        </Typography>
                        {savedRequirements.length > 0 && (
                            <Chip label={savedRequirements.length} size="small" />
                        )}
                    </Box>
                    <Button
                        variant="outlined"
                        startIcon={<AddIcon />}
                        onClick={() => { setEditTarget(null); setFormOpen(true); }}
                    >
                        Add Manual
                    </Button>
                </Box>

                {loadingSaved ? (
                    [1, 2, 3].map((n) => <Skeleton key={n} height={42} sx={{ mb: 0.5 }} />)
                ) : savedRequirements.length === 0 ? (
                    <Paper variant="outlined" sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
                        <AcceptedIcon sx={{ fontSize: 40, opacity: 0.3, mb: 1 }} />
                        <Typography>
                            No requirements yet. Accept suggestions above or add one manually.
                        </Typography>
                    </Paper>
                ) : (
                    <Paper variant="outlined">
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>Principle</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>Source</TableCell>
                                    <TableCell sx={{ fontWeight: 600 }}>Rules</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 600 }}>Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {savedRequirements.map((req: Requirement) => (
                                    <TableRow key={req.id} hover>
                                        <TableCell>
                                            <Typography variant="body2" fontWeight={500}>
                                                {req.name}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={req.principle}
                                                size="small"
                                                sx={{
                                                    bgcolor: principleColor[req.principle] + '22',
                                                    color: principleColor[req.principle],
                                                    fontWeight: 600,
                                                }}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={req.elicited_automatically ? 'Auto' : 'Manual'}
                                                size="small"
                                                variant="outlined"
                                                color={req.elicited_automatically ? 'primary' : 'default'}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="caption" color="text.secondary">
                                                {req.specification?.rules?.length ?? 0} rule(s)
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Tooltip title="Edit">
                                                <IconButton
                                                    size="small"
                                                    onClick={() => { setEditTarget(req); setFormOpen(true); }}
                                                >
                                                    <EditIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="Delete">
                                                <IconButton
                                                    size="small"
                                                    color="error"
                                                    onClick={() => deleteMutation.mutate(req.id ?? '')}
                                                >
                                                    <DeleteIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </Paper>
                )}
            </Box>

            {/* ── Requirement Form Dialog ───────────────────────────────────── */}
            <RequirementForm
                open={formOpen}
                onClose={() => setFormOpen(false)}
                initialValues={editTarget ?? undefined}
                onSubmit={handleFormSubmit}
            />
        </Box>
    );
}
