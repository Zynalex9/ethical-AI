// Project detail page with model/dataset upload

import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Box,
    Container,
    Typography,
    Button,
    Card,
    CardContent,
    Tabs,
    Tab,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    IconButton,
    Chip,
    CircularProgress,
    Alert,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    LinearProgress,
    Checkbox,
    Tooltip,
    Stack,
} from '@mui/material';
import {
    ArrowBack as BackIcon,
    CloudUpload as UploadIcon,
    Delete as DeleteIcon,
    PlayArrow as RunIcon,
    ModelTraining as ModelIcon,
    Storage as DatasetIcon,
    Assessment as ValidationIcon,
    Assignment as RequirementIcon,
    AutoFixHigh as ElicitIcon,
    AccountTree as TraceIcon,
    ContentCopy as DuplicateIcon,
    Edit as EditIcon,
    CompareArrows as CompareIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi, modelsApi, datasetsApi, validationApi, requirementsApi, traceabilityApi, templatesApi, getApiErrorMessage } from '../services/api';
import BenchmarkDatasetLoader from '../components/BenchmarkDatasetLoader';
import TraceabilityMatrix from '../components/TraceabilityMatrix';
import ScheduleSettings from '../components/ScheduleSettings';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer } from 'recharts';
import type { Template } from '../types';

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

// ---------------------------------------------------------------------------
// Comparison Modal
// ---------------------------------------------------------------------------
type MetricDetail = { value: number | null; threshold: number | null; passed: boolean | null };
type PrincipleMetrics = Record<string, MetricDetail>;

function CompareModal({ open, onClose, runA, runB }: { open: boolean; onClose: () => void; runA: any; runB: any }) {
    if (!runA || !runB) return null;

    const principles: Array<{ key: 'fairness' | 'transparency' | 'privacy'; label: string }> = [
        { key: 'fairness', label: 'Fairness' },
        { key: 'transparency', label: 'Transparency' },
        { key: 'privacy', label: 'Privacy' },
    ];

    const fmt = (v: number | null | undefined) => (v == null ? '\u2014' : Number(v).toFixed(4));

    const deltaColor = (delta: number | null, mkey: string): string => {
        if (delta == null) return 'text.primary';
        const lowerBetter = ['difference', 'disparity'];
        const goodDirection = lowerBetter.some((k) => mkey.includes(k)) ? delta < 0 : delta > 0;
        if (delta === 0) return 'text.secondary';
        return goodDirection ? 'success.main' : 'error.main';
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
            <DialogTitle>
                Compare Validation Runs
                <Typography variant="body2" color="text.secondary">
                    Run A: {new Date(runA.started_at).toLocaleString()} &nbsp;·&nbsp;
                    Run B: {new Date(runB.started_at).toLocaleString()}
                </Typography>
            </DialogTitle>
            <DialogContent dividers>
                {principles.map(({ key, label }) => {
                    const metricsA: PrincipleMetrics = runA.validations?.[key]?.metrics || {};
                    const metricsB: PrincipleMetrics = runB.validations?.[key]?.metrics || {};
                    const allKeys = Array.from(new Set([...Object.keys(metricsA), ...Object.keys(metricsB)]));
                    const eitherRun = runA.validations?.[key]?.completed || runB.validations?.[key]?.completed;
                    if (!eitherRun) return null;
                    return (
                        <Box key={key} sx={{ mb: 4 }}>
                            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1, textTransform: 'uppercase', letterSpacing: 1, color: 'primary.main' }}>
                                {label}
                            </Typography>
                            {allKeys.length === 0 ? (
                                <Typography variant="body2" color="text.secondary">No per-metric breakdown available.</Typography>
                            ) : (
                                <Table size="small">
                                    <TableHead>
                                        <TableRow sx={{ bgcolor: 'action.hover' }}>
                                            <TableCell sx={{ fontWeight: 700 }}>Metric</TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 700 }}>Run A &nbsp;<Typography component="span" variant="caption" color="text.secondary">{new Date(runA.started_at).toLocaleDateString()}</Typography></TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 700 }}>Run B &nbsp;<Typography component="span" variant="caption" color="text.secondary">{new Date(runB.started_at).toLocaleDateString()}</Typography></TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 700 }}>Delta (B − A)</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {allKeys.map((mkey) => {
                                            const a = metricsA[mkey];
                                            const b = metricsB[mkey];
                                            const delta = a?.value != null && b?.value != null ? b.value - a.value : null;
                                            return (
                                                <TableRow key={mkey} hover>
                                                    <TableCell sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                                                        {mkey.replace(/_/g, ' ')}
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        {a ? (
                                                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
                                                                <Typography variant="body2">{fmt(a.value)}</Typography>
                                                                <Chip label={a.passed ? 'PASS' : 'FAIL'} color={a.passed ? 'success' : 'error'} size="small" />
                                                            </Box>
                                                        ) : <Typography variant="body2" color="text.disabled">&mdash;</Typography>}
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        {b ? (
                                                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
                                                                <Typography variant="body2">{fmt(b.value)}</Typography>
                                                                <Chip label={b.passed ? 'PASS' : 'FAIL'} color={b.passed ? 'success' : 'error'} size="small" />
                                                            </Box>
                                                        ) : <Typography variant="body2" color="text.disabled">&mdash;</Typography>}
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        <Typography variant="body2" sx={{ fontWeight: 700, color: deltaColor(delta, mkey) }}>
                                                            {delta == null ? '\u2014' : `${delta > 0 ? '+' : ''}${delta.toFixed(4)}`}
                                                        </Typography>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            )}
                        </Box>
                    );
                })}
                {/* Overall verdict */}
                <Box sx={{ display: 'flex', gap: 4, mt: 1, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                    <Box>
                        <Typography variant="caption" color="text.secondary">Run A Overall</Typography>
                        <Box sx={{ mt: 0.5 }}><Chip label={runA.overall_passed ? 'PASSED' : 'FAILED'} color={runA.overall_passed ? 'success' : 'error'} /></Box>
                    </Box>
                    <Box>
                        <Typography variant="caption" color="text.secondary">Run B Overall</Typography>
                        <Box sx={{ mt: 0.5 }}><Chip label={runB.overall_passed ? 'PASSED' : 'FAILED'} color={runB.overall_passed ? 'success' : 'error'} /></Box>
                    </Box>
                </Box>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}
// ---------------------------------------------------------------------------

function TabPanel({ children, value, index }: TabPanelProps) {
    return (
        <div hidden={value !== index} style={{ paddingTop: 24 }}>
            {value === index && children}
        </div>
    );
}

// File upload area component
function FileUploadArea({
    accept,
    onFileSelect,
    uploading,
    progress,
    selectedFile,
}: {
    accept: string;
    onFileSelect: (file: File) => void;
    uploading: boolean;
    progress: number;
    selectedFile?: File | null;
}) {
    const [dragOver, setDragOver] = useState(false);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) onFileSelect(file);
    }, [onFileSelect]);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(true);
    }, []);

    const handleDragLeave = useCallback(() => {
        setDragOver(false);
    }, []);

    return (
        <Box
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            sx={{
                border: '2px dashed',
                borderColor: dragOver ? 'primary.main' : 'divider',
                borderRadius: 2,
                p: 4,
                textAlign: 'center',
                backgroundColor: dragOver ? 'rgba(102, 126, 234, 0.1)' : 'transparent',
                transition: 'all 0.2s',
                cursor: uploading ? 'not-allowed' : 'pointer',
            }}
        >
            {uploading ? (
                <Box>
                    <CircularProgress size={48} sx={{ mb: 2 }} />
                    <Typography>Uploading...</Typography>
                    <LinearProgress variant="determinate" value={progress} sx={{ mt: 2, mx: 'auto', maxWidth: 300 }} />
                </Box>
            ) : (
                <>
                    <UploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    {selectedFile ? (
                        <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
                            {selectedFile.name}
                        </Typography>
                    ) : (
                        <>
                            <Typography variant="h6" gutterBottom>
                                Drag & drop file here
                            </Typography>
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                                or click to browse
                            </Typography>
                        </>
                    )}
                    <Button
                        variant="outlined"
                        component="label"
                        sx={{ mt: 1 }}
                    >
                        {selectedFile ? 'Change File' : 'Select File'}
                        <input
                            type="file"
                            hidden
                            accept={accept}
                            onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) onFileSelect(file);
                                // Reset so the same file can be re-selected after a validation error
                                e.target.value = '';
                            }}
                        />
                    </Button>
                </>
            )}
        </Box>
    );
}

export default function ProjectDetailPage() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    const [tab, setTab] = useState(0);
    const [uploadModelOpen, setUploadModelOpen] = useState(false);
    const [uploadDatasetOpen, setUploadDatasetOpen] = useState(false);
    const [benchmarkLoaderOpen, setBenchmarkLoaderOpen] = useState(false);
    const [modelName, setModelName] = useState('');
    const [datasetName, setDatasetName] = useState('');
    const [pendingModelFile, setPendingModelFile] = useState<File | null>(null);
    const [pendingDatasetFile, setPendingDatasetFile] = useState<File | null>(null);
    const [sensitiveAttrs, setSensitiveAttrs] = useState('');
    const [targetColumn, setTargetColumn] = useState('');
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [error, setError] = useState('');
    const [compareSelected, setCompareSelected] = useState<Set<string>>(new Set());
    const [compareModalOpen, setCompareModalOpen] = useState(false);

    const MAX_UPLOAD_SIZE_BYTES = 500 * 1024 * 1024;
    const MODEL_EXTENSIONS = new Set(['.pkl', '.joblib', '.pickle', '.h5', '.keras', '.pt', '.pth', '.onnx']);
    const DATASET_EXTENSIONS = new Set(['.csv', '.xlsx', '.parquet']);

    const getFileExtension = (filename: string): string => {
        const dot = filename.lastIndexOf('.');
        return dot >= 0 ? filename.slice(dot).toLowerCase() : '';
    };

    // Fetch project
    const { data: project, isLoading: projectLoading } = useQuery({
        queryKey: ['project', id],
        queryFn: () => projectsApi.get(id!),
        enabled: !!id,
    });

    // Fetch models
    const { data: models, isLoading: modelsLoading } = useQuery({
        queryKey: ['models', id],
        queryFn: () => modelsApi.list(id!),
        enabled: !!id,
    });

    // Fetch datasets
    const { data: datasets, isLoading: datasetsLoading } = useQuery({
        queryKey: ['datasets', id],
        queryFn: () => datasetsApi.list(id!),
        enabled: !!id,
    });

    // Fetch validation history
    const { data: savedRequirements = [] } = useQuery({
        queryKey: ['requirements', id],
        queryFn: () => requirementsApi.listByProject(id!),
        enabled: !!id,
    });

    // Fetch templates for requirement source lookup (Phase 5)
    const { data: allTemplates = [] } = useQuery<Template[]>({
        queryKey: ['templates'],
        queryFn: () => templatesApi.list(),
        enabled: !!id,
    });
    const templateMap = new Map(allTemplates.map((t) => [t.id, t]));

    // Duplicate requirement mutation (Phase 5 – 6.7)
    const duplicateRequirementMutation = useMutation({
        mutationFn: (req: any) =>
            requirementsApi.create(id!, {
                name: `${req.name} (Copy)`,
                principle: req.principle,
                description: req.description,
                specification: req.specification,
                based_on_template_id: req.based_on_template_id,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['requirements', id] });
        },
    });

    const { data: validationHistory, isLoading: validationsLoading } = useQuery({
        queryKey: ['validations', id],
        queryFn: () => validationApi.getHistory(id!),
        enabled: !!id && tab === 3,
    });

    const { data: traceabilityData, isLoading: traceabilityLoading, error: traceabilityError, refetch: refetchTraceability } = useQuery({
        queryKey: ['traceability', id],
        queryFn: () => traceabilityApi.getMatrix(id!),
        enabled: !!id && tab === 4,
        refetchOnMount: 'always',
    });

    // Upload model
    const handleModelUpload = async (file: File) => {
        if (!modelName.trim()) {
            setError('Please enter a model name');
            return;
        }

        const ext = getFileExtension(file.name);
        if (!MODEL_EXTENSIONS.has(ext)) {
            setError('Unsupported model format. Allowed: .pkl, .joblib, .pickle, .h5, .keras, .pt, .pth, .onnx');
            return;
        }

        if (file.size <= 0) {
            setError('Selected model file is empty');
            return;
        }

        if (file.size > MAX_UPLOAD_SIZE_BYTES) {
            setError('Model file exceeds 500 MB upload limit');
            return;
        }

        setUploading(true);
        setError('');

        try {
            await modelsApi.upload(id!, file, modelName);
            queryClient.invalidateQueries({ queryKey: ['models', id] });
            queryClient.invalidateQueries({ queryKey: ['project', id] });
            setUploadModelOpen(false);
            setModelName('');
            setPendingModelFile(null);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Model upload failed'));
        } finally {
            setUploading(false);
            setUploadProgress(0);
        }
    };

    // Upload dataset
    const handleDatasetUpload = async (file: File) => {
        if (!datasetName.trim()) {
            setError('Please enter a dataset name');
            return;
        }

        const ext = getFileExtension(file.name);
        if (!DATASET_EXTENSIONS.has(ext)) {
            setError('Unsupported dataset format. Allowed: .csv, .xlsx, .parquet');
            return;
        }

        if (file.size <= 0) {
            setError('Selected dataset file is empty');
            return;
        }

        if (file.size > MAX_UPLOAD_SIZE_BYTES) {
            setError('Dataset file exceeds 500 MB upload limit');
            return;
        }

        setUploading(true);
        setError('');

        try {
            await datasetsApi.upload(id!, file, datasetName, sensitiveAttrs, targetColumn);
            queryClient.invalidateQueries({ queryKey: ['datasets', id] });
            queryClient.invalidateQueries({ queryKey: ['project', id] });
            setUploadDatasetOpen(false);
            setDatasetName('');
            setSensitiveAttrs('');
            setTargetColumn('');
            setPendingDatasetFile(null);
        } catch (err) {
            setError(getApiErrorMessage(err, 'Dataset upload failed'));
        } finally {
            setUploading(false);
            setUploadProgress(0);
        }
    };

    // Delete model
    const handleDeleteModel = async (modelId: string) => {
        if (!confirm('Are you sure you want to delete this model?')) return;

        try {
            await modelsApi.delete(modelId);
            queryClient.invalidateQueries({ queryKey: ['models', id] });
            queryClient.invalidateQueries({ queryKey: ['project', id] });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to delete model');
        }
    };

    // Delete dataset
    const handleDeleteDataset = async (datasetId: string) => {
        if (!confirm('Are you sure you want to delete this dataset?')) return;

        try {
            await datasetsApi.delete(datasetId);
            queryClient.invalidateQueries({ queryKey: ['datasets', id] });
            queryClient.invalidateQueries({ queryKey: ['project', id] });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to delete dataset');
        }
    };

    if (projectLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 8 }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!project) {
        return (
            <Container maxWidth="xl" sx={{ py: 4 }}>
                <Alert severity="error">Project not found</Alert>
            </Container>
        );
    }

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 4 }}>
                <IconButton onClick={() => navigate('/projects')} sx={{ mr: 2 }}>
                    <BackIcon />
                </IconButton>
                <Box sx={{ flex: 1 }}>
                    <Typography variant="h4" sx={{ fontWeight: 700 }}>
                        {project.name}
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        {project.description || 'No description'}
                    </Typography>
                </Box>
                <Button
                    variant="contained"
                    startIcon={<RunIcon />}
                    onClick={() => navigate(`/projects/${id}/validate`)}
                >
                    Run Validation
                </Button>
                <Button
                    variant="outlined"
                    startIcon={<TraceIcon />}
                    onClick={() => navigate(`/projects/${id}/traceability`)}
                    sx={{ ml: 1 }}
                >
                    Traceability
                </Button>
            </Box>

            {/* Tabs */}
            <Tabs value={tab} onChange={(_, v) => setTab(v)}>
                <Tab icon={<ModelIcon />} iconPosition="start" label={`Models (${models?.length || 0})`} />
                <Tab icon={<DatasetIcon />} iconPosition="start" label={`Datasets (${datasets?.length || 0})`} />
                <Tab icon={<RequirementIcon />} iconPosition="start" label={`Requirements (${savedRequirements.length})`} />
                <Tab icon={<ValidationIcon />} iconPosition="start" label="Validations" />
                <Tab icon={<TraceIcon />} iconPosition="start" label="Traceability" />
            </Tabs>

            {/* Models Tab */}
            <TabPanel value={tab} index={0}>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
                    <Button
                        variant="contained"
                        startIcon={<UploadIcon />}
                        onClick={() => setUploadModelOpen(true)}
                    >
                        Upload Model
                    </Button>
                </Box>

                {modelsLoading ? (
                    <CircularProgress />
                ) : models?.length === 0 ? (
                    <Card>
                        <CardContent sx={{ textAlign: 'center', py: 6 }}>
                            <ModelIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography variant="h6" color="text.secondary">
                                No models uploaded yet
                            </Typography>
                            <Button
                                variant="outlined"
                                startIcon={<UploadIcon />}
                                sx={{ mt: 2 }}
                                onClick={() => setUploadModelOpen(true)}
                            >
                                Upload First Model
                            </Button>
                        </CardContent>
                    </Card>
                ) : (
                    <TableContainer component={Card}>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Type</TableCell>
                                    <TableCell>Version</TableCell>
                                    <TableCell>Size</TableCell>
                                    <TableCell>Uploaded</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {models?.map((model: any) => (
                                    <TableRow key={model.id}>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                                <ModelIcon sx={{ mr: 1, color: 'primary.main' }} />
                                                {model.name}
                                            </Box>
                                        </TableCell>
                                        <TableCell>
                                            <Chip label={model.model_type} size="small" />
                                        </TableCell>
                                        <TableCell>{model.version}</TableCell>
                                        <TableCell>{(model.file_size / 1024).toFixed(1)} KB</TableCell>
                                        <TableCell>
                                            {new Date(model.uploaded_at).toLocaleDateString()}
                                        </TableCell>
                                        <TableCell align="right">
                                            <IconButton
                                                size="small"
                                                color="error"
                                                onClick={() => handleDeleteModel(model.id)}
                                            >
                                                <DeleteIcon />
                                            </IconButton>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </TabPanel>

            {/* Datasets Tab */}
            <TabPanel value={tab} index={1}>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mb: 2 }}>
                    <Button
                        variant="outlined"
                        onClick={() => setBenchmarkLoaderOpen(true)}
                    >
                        Load Benchmark Dataset
                    </Button>
                    <Button
                        variant="contained"
                        startIcon={<UploadIcon />}
                        onClick={() => setUploadDatasetOpen(true)}
                    >
                        Upload Dataset
                    </Button>
                </Box>

                {datasetsLoading ? (
                    <CircularProgress />
                ) : datasets?.length === 0 ? (
                    <Card>
                        <CardContent sx={{ textAlign: 'center', py: 6 }}>
                            <DatasetIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography variant="h6" color="text.secondary">
                                No datasets uploaded yet
                            </Typography>
                            <Button
                                variant="outlined"
                                startIcon={<UploadIcon />}
                                sx={{ mt: 2 }}
                                onClick={() => setUploadDatasetOpen(true)}
                            >
                                Upload First Dataset
                            </Button>
                        </CardContent>
                    </Card>
                ) : (
                    <TableContainer component={Card}>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Rows</TableCell>
                                    <TableCell>Columns</TableCell>
                                    <TableCell>Sensitive Attrs</TableCell>
                                    <TableCell>Uploaded</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {datasets?.map((dataset: any) => (
                                    <TableRow key={dataset.id}>
                                        <TableCell>
                                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                                <DatasetIcon sx={{ mr: 1, color: 'secondary.main' }} />
                                                {dataset.name}
                                            </Box>
                                        </TableCell>
                                        <TableCell>{dataset.row_count?.toLocaleString()}</TableCell>
                                        <TableCell>{dataset.column_count}</TableCell>
                                        <TableCell>
                                            {dataset.sensitive_attributes?.length > 0 ? (
                                                dataset.sensitive_attributes.map((attr: string) => (
                                                    <Chip key={attr} label={attr} size="small" sx={{ mr: 0.5 }} />
                                                ))
                                            ) : (
                                                <Typography variant="body2" color="text.disabled">None</Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            {new Date(dataset.uploaded_at).toLocaleDateString()}
                                        </TableCell>
                                        <TableCell align="right">
                                            <IconButton
                                                size="small"
                                                color="error"
                                                onClick={() => handleDeleteDataset(dataset.id)}
                                            >
                                                <DeleteIcon />
                                            </IconButton>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </TabPanel>

            {/* Requirements Tab (Phase 5 – 6.7 improved) */}
            <TabPanel value={tab} index={2}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                    <Typography variant="body2" color="text.secondary">
                        Define ethical requirements and use Cognitive RE to auto-generate them from your data and model.
                    </Typography>
                    <Button
                        variant="contained"
                        startIcon={<ElicitIcon />}
                        onClick={() => navigate(`/projects/${id}/requirements/elicit`)}
                    >
                        Elicit Requirements
                    </Button>
                </Box>
                {savedRequirements.length === 0 ? (
                    <Card>
                        <CardContent sx={{ textAlign: 'center', py: 6 }}>
                            <RequirementIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography variant="h6" color="text.secondary">
                                No requirements defined yet
                            </Typography>
                            <Button
                                variant="outlined"
                                startIcon={<ElicitIcon />}
                                sx={{ mt: 2 }}
                                onClick={() => navigate(`/projects/${id}/requirements/elicit`)}
                            >
                                Elicit Requirements
                            </Button>
                        </CardContent>
                    </Card>
                ) : (
                    <TableContainer component={Card}>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Principle</TableCell>
                                    <TableCell>Source</TableCell>
                                    <TableCell>Rules</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {savedRequirements.map((req: any) => {
                                    const srcTemplate = req.based_on_template_id
                                        ? templateMap.get(req.based_on_template_id)
                                        : null;
                                    const sourceLabel = srcTemplate
                                        ? `Template (${srcTemplate.template_id})`
                                        : req.elicited_automatically
                                        ? 'Auto-generated'
                                        : 'Manual';
                                    const sourceColor: 'primary' | 'secondary' | 'default' = srcTemplate
                                        ? 'secondary'
                                        : req.elicited_automatically
                                        ? 'primary'
                                        : 'default';
                                    return (
                                        <TableRow key={req.id} hover>
                                            <TableCell>
                                                <Typography variant="body2" fontWeight={500}>{req.name}</Typography>
                                                {req.description && (
                                                    <Typography variant="caption" color="text.secondary">{req.description}</Typography>
                                                )}
                                                {srcTemplate && (
                                                    <Chip
                                                        label={`From ${srcTemplate.name}`}
                                                        size="small"
                                                        variant="outlined"
                                                        color="secondary"
                                                        sx={{ mt: 0.5, display: 'block', width: 'fit-content' }}
                                                    />
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <Chip label={req.principle} size="small" />
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={sourceLabel}
                                                    size="small"
                                                    variant="outlined"
                                                    color={sourceColor}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="caption" color="text.secondary">
                                                    {req.specification?.rules?.length ?? 0} rule(s)
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right">
                                                <Button
                                                    size="small"
                                                    startIcon={<EditIcon />}
                                                    onClick={() => navigate(`/projects/${id}/requirements/elicit`)}
                                                >
                                                    Edit
                                                </Button>
                                                <Button
                                                    size="small"
                                                    startIcon={<DuplicateIcon />}
                                                    onClick={() => duplicateRequirementMutation.mutate(req)}
                                                    disabled={duplicateRequirementMutation.isPending}
                                                >
                                                    Duplicate
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </TabPanel>

            {/* Validations Tab */}
            <TabPanel value={tab} index={3}>
                {/* Scheduled Re-Validation Settings */}
                {id && <ScheduleSettings projectId={id} />}

                {validationsLoading ? (
                    <CircularProgress />
                ) : validationHistory?.length === 0 ? (
                    <Card>
                        <CardContent sx={{ textAlign: 'center', py: 6 }}>
                            <ValidationIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography variant="h6" color="text.secondary">
                                No validations run yet
                            </Typography>
                            <Button
                                variant="contained"
                                startIcon={<RunIcon />}
                                sx={{ mt: 2 }}
                                onClick={() => navigate(`/projects/${id}/validate`)}
                            >
                                Run First Validation
                            </Button>
                        </CardContent>
                    </Card>
                ) : (
                    <>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Typography variant="h6">Validation History</Typography>
                                {compareSelected.size > 0 && (
                                    <Typography variant="caption" color="text.secondary">
                                        {compareSelected.size} selected
                                    </Typography>
                                )}
                            </Box>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                                <Tooltip title={compareSelected.size !== 2 ? 'Select exactly 2 runs to compare' : ''}>
                                    <span>
                                        <Button
                                            variant="outlined"
                                            startIcon={<CompareIcon />}
                                            disabled={compareSelected.size !== 2}
                                            onClick={() => setCompareModalOpen(true)}
                                        >
                                            Compare ({compareSelected.size}/2)
                                        </Button>
                                    </span>
                                </Tooltip>
                                <Button
                                    variant="contained"
                                    startIcon={<RunIcon />}
                                    onClick={() => navigate(`/projects/${id}/validate`)}
                                >
                                    Run New Validation
                                </Button>
                            </Box>
                        </Box>

                        {/* Fairness Metrics Over Time Chart */}
                        {(() => {
                            const chartRuns = (validationHistory || [])
                                .filter((v: any) => v.validations?.fairness?.completed && v.validations.fairness.metrics && Object.keys(v.validations.fairness.metrics).length > 0)
                                .reverse(); // oldest first
                            if (chartRuns.length < 2) {
                                return (
                                    <Card sx={{ mb: 3 }}>
                                        <CardContent sx={{ textAlign: 'center', py: 3 }}>
                                            <Typography variant="body2" color="text.secondary">
                                                Run at least 2 validations with fairness metrics to see the trend chart.
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                );
                            }
                            // Collect all metric keys across runs
                            const metricKeys = new Set<string>();
                            chartRuns.forEach((v: any) => {
                                Object.keys(v.validations.fairness.metrics).forEach((k: string) => metricKeys.add(k));
                            });
                            const chartData = chartRuns.map((v: any) => {
                                const point: Record<string, any> = { date: new Date(v.started_at).toLocaleDateString() };
                                metricKeys.forEach((k) => {
                                    const m = v.validations.fairness.metrics[k];
                                    if (m) point[k] = Number(m.value);
                                });
                                return point;
                            });
                            const COLORS = ['#2e7d32', '#1565c0', '#e65100', '#6a1b9a', '#c62828', '#00838f'];
                            return (
                                <Card sx={{ mb: 3 }}>
                                    <CardContent>
                                        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                                            Fairness Metrics Over Time
                                        </Typography>
                                        <ResponsiveContainer width="100%" height={280}>
                                            <LineChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" />
                                                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                                                <YAxis tick={{ fontSize: 11 }} domain={[0, 'auto']} />
                                                <RechartsTooltip />
                                                <Legend />
                                                {Array.from(metricKeys).map((key, idx) => (
                                                    <Line
                                                        key={key}
                                                        type="monotone"
                                                        dataKey={key}
                                                        name={key.replace(/_/g, ' ')}
                                                        stroke={COLORS[idx % COLORS.length]}
                                                        strokeWidth={2}
                                                        dot={{ r: 4 }}
                                                        connectNulls
                                                    />
                                                ))}
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </CardContent>
                                </Card>
                            );
                        })()}
                        
                        <TableContainer component={Card}>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell padding="checkbox">
                                            <Tooltip title="Select to compare (max 2)">
                                                <span><Checkbox disabled /></span>
                                            </Tooltip>
                                        </TableCell>
                                        <TableCell>Date</TableCell>
                                        <TableCell>Model</TableCell>
                                        <TableCell>Dataset</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Fairness</TableCell>
                                        <TableCell>Transparency</TableCell>
                                        <TableCell>Privacy</TableCell>
                                        <TableCell align="right">Actions</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {validationHistory?.map((validation: any) => (
                                        <TableRow
                                            key={validation.suite_id}
                                            selected={compareSelected.has(validation.suite_id)}
                                            sx={{ '&.Mui-selected': { bgcolor: 'action.selected' } }}
                                        >
                                            <TableCell padding="checkbox">
                                                <Checkbox
                                                    checked={compareSelected.has(validation.suite_id)}
                                                    disabled={!compareSelected.has(validation.suite_id) && compareSelected.size >= 2}
                                                    onChange={(e) => {
                                                        setCompareSelected((prev) => {
                                                            const next = new Set(prev);
                                                            if (e.target.checked) next.add(validation.suite_id);
                                                            else next.delete(validation.suite_id);
                                                            return next;
                                                        });
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                {new Date(validation.started_at).toLocaleDateString()}
                                                <br />
                                                <Typography variant="caption" color="text.secondary">
                                                    {new Date(validation.started_at).toLocaleTimeString()}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>{validation.model_name}</TableCell>
                                            <TableCell>{validation.dataset_name}</TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={validation.overall_passed ? 'PASSED' : 'FAILED'}
                                                    color={validation.overall_passed ? 'success' : 'error'}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                {validation.validations.fairness.completed ? (
                                                    <Chip
                                                        label={`${validation.validations.fairness.passed_count}/${validation.validations.fairness.metrics_count}`}
                                                        color={validation.validations.fairness.passed_count === validation.validations.fairness.metrics_count ? 'success' : 'warning'}
                                                        size="small"
                                                    />
                                                ) : (
                                                    <Chip label="N/A" size="small" variant="outlined" />
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                {validation.validations.transparency.completed ? (
                                                    <Chip
                                                        label={`${validation.validations.transparency.passed_count}/${validation.validations.transparency.metrics_count}`}
                                                        color={validation.validations.transparency.passed_count === validation.validations.transparency.metrics_count ? 'success' : 'warning'}
                                                        size="small"
                                                    />
                                                ) : (
                                                    <Chip label="N/A" size="small" variant="outlined" />
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                {validation.validations.privacy.completed ? (
                                                    <Chip
                                                        label={`${validation.validations.privacy.passed_count}/${validation.validations.privacy.metrics_count}`}
                                                        color={validation.validations.privacy.passed_count === validation.validations.privacy.metrics_count ? 'success' : 'warning'}
                                                        size="small"
                                                    />
                                                ) : (
                                                    <Chip label="N/A" size="small" variant="outlined" />
                                                )}
                                            </TableCell>
                                            <TableCell align="right">
                                                <Button
                                                    size="small"
                                                    onClick={() => navigate(`/projects/${id}/validate?suite=${validation.suite_id}`)}
                                                >
                                                    View Details
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>

                        {/* Compare modal */}
                        {(() => {
                            const [idA, idB] = Array.from(compareSelected);
                            const runA = validationHistory?.find((v: any) => v.suite_id === idA);
                            const runB = validationHistory?.find((v: any) => v.suite_id === idB);
                            return (
                                <CompareModal
                                    open={compareModalOpen}
                                    onClose={() => setCompareModalOpen(false)}
                                    runA={runA}
                                    runB={runB}
                                />
                            );
                        })()}
                    </>
                )}
            </TabPanel>

            {/* Traceability Tab */}
            <TabPanel value={tab} index={4}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6">Requirement Traceability Matrix</Typography>
                    <Stack direction="row" spacing={1}>
                        <Button
                            variant="outlined"
                            onClick={() => refetchTraceability()}
                            disabled={traceabilityLoading}
                        >
                            Refresh
                        </Button>
                        <Button
                            variant="outlined"
                            startIcon={<TraceIcon />}
                            onClick={() => navigate(`/projects/${id}/traceability`)}
                        >
                            Full Traceability View
                        </Button>
                    </Stack>
                </Box>
                {traceabilityError && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                        Failed to load traceability data: {(traceabilityError as Error).message}
                    </Alert>
                )}
                <TraceabilityMatrix
                    traces={traceabilityData?.traces || []}
                    loading={traceabilityLoading}
                    onViewRootCause={(validationId) => navigate(`/projects/${id}/traceability?rootCause=${validationId}`)}
                />
            </TabPanel>

            {/* Upload Model Dialog */}
            <Dialog
                open={uploadModelOpen}
                onClose={() => { setUploadModelOpen(false); setPendingModelFile(null); setError(''); }}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>Upload Model</DialogTitle>
                <DialogContent>
                    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                    <TextField
                        label="Model Name"
                        fullWidth
                        value={modelName}
                        onChange={(e) => setModelName(e.target.value)}
                        sx={{ mb: 3, mt: 1 }}
                    />

                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Supported formats: .pkl, .joblib, .h5, .keras, .pt, .pth, .onnx
                    </Typography>

                    <FileUploadArea
                        accept=".pkl,.joblib,.pickle,.h5,.keras,.pt,.pth,.onnx"
                        onFileSelect={(f) => { setError(''); setPendingModelFile(f); }}
                        uploading={uploading}
                        progress={uploadProgress}
                        selectedFile={pendingModelFile}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => { setUploadModelOpen(false); setPendingModelFile(null); setError(''); }}>Cancel</Button>
                    <Button
                        variant="contained"
                        disabled={!pendingModelFile || uploading}
                        onClick={() => pendingModelFile && handleModelUpload(pendingModelFile)}
                    >
                        Upload
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Upload Dataset Dialog */}
            <Dialog
                open={uploadDatasetOpen}
                onClose={() => { setUploadDatasetOpen(false); setPendingDatasetFile(null); setError(''); }}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>Upload Dataset</DialogTitle>
                <DialogContent>
                    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                    <TextField
                        label="Dataset Name"
                        fullWidth
                        value={datasetName}
                        onChange={(e) => setDatasetName(e.target.value)}
                        sx={{ mb: 2, mt: 1 }}
                    />

                    <TextField
                        label="Sensitive Attributes (comma-separated)"
                        fullWidth
                        value={sensitiveAttrs}
                        onChange={(e) => setSensitiveAttrs(e.target.value)}
                        placeholder="e.g., gender, race, age"
                        helperText="Columns to use for fairness analysis"
                        sx={{ mb: 2 }}
                    />

                    <TextField
                        label="Target Column"
                        fullWidth
                        value={targetColumn}
                        onChange={(e) => setTargetColumn(e.target.value)}
                        placeholder="e.g., approved, label"
                        helperText="The prediction target column"
                        sx={{ mb: 3 }}
                    />

                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Supported formats: CSV, Excel (.xlsx), Parquet
                    </Typography>

                    <FileUploadArea
                        accept=".csv,.xlsx,.parquet"
                        onFileSelect={(f) => { setError(''); setPendingDatasetFile(f); }}
                        uploading={uploading}
                        progress={uploadProgress}
                        selectedFile={pendingDatasetFile}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => { setUploadDatasetOpen(false); setPendingDatasetFile(null); setError(''); }}>Cancel</Button>
                    <Button
                        variant="contained"
                        disabled={!pendingDatasetFile || uploading}
                        onClick={() => pendingDatasetFile && handleDatasetUpload(pendingDatasetFile)}
                    >
                        Upload
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Benchmark Dataset Loader */}
            <BenchmarkDatasetLoader
                open={benchmarkLoaderOpen}
                onClose={() => setBenchmarkLoaderOpen(false)}
                projectId={id!}
                onSuccess={(datasetName) => {
                    queryClient.invalidateQueries({ queryKey: ['datasets', id] });
                    alert(`Successfully loaded ${datasetName} dataset!`);
                }}
            />
        </Container>
    );
}
