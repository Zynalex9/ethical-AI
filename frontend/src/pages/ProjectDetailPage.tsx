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
} from '@mui/icons-material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { projectsApi, modelsApi, datasetsApi, validationApi, requirementsApi } from '../services/api';
import BenchmarkDatasetLoader from '../components/BenchmarkDatasetLoader';

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

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
}: {
    accept: string;
    onFileSelect: (file: File) => void;
    uploading: boolean;
    progress: number;
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
                    <Typography variant="h6" gutterBottom>
                        Drag & drop file here
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        or click to browse
                    </Typography>
                    <Button
                        variant="outlined"
                        component="label"
                        sx={{ mt: 2 }}
                    >
                        Select File
                        <input
                            type="file"
                            hidden
                            accept={accept}
                            onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) onFileSelect(file);
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
    const [sensitiveAttrs, setSensitiveAttrs] = useState('');
    const [targetColumn, setTargetColumn] = useState('');
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [error, setError] = useState('');

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

    const { data: validationHistory, isLoading: validationsLoading } = useQuery({
        queryKey: ['validations', id],
        queryFn: () => validationApi.getHistory(id!),
        enabled: !!id && tab === 3,
    });

    // Upload model
    const handleModelUpload = async (file: File) => {
        if (!modelName.trim()) {
            setError('Please enter a model name');
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
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed');
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

        setUploading(true);
        setError('');

        try {
            // Create FormData
            const formData = new FormData();
            formData.append('file', file);
            formData.append('name', datasetName);
            formData.append('project_id', id!);
            if (sensitiveAttrs) formData.append('sensitive_attributes', sensitiveAttrs);
            if (targetColumn) formData.append('target_column', targetColumn);

            await datasetsApi.upload(id!, file, datasetName);
            queryClient.invalidateQueries({ queryKey: ['datasets', id] });
            queryClient.invalidateQueries({ queryKey: ['project', id] });
            setUploadDatasetOpen(false);
            setDatasetName('');
            setSensitiveAttrs('');
            setTargetColumn('');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed');
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
            </Box>

            {/* Tabs */}
            <Tabs value={tab} onChange={(_, v) => setTab(v)}>
                <Tab icon={<ModelIcon />} iconPosition="start" label={`Models (${models?.length || 0})`} />
                <Tab icon={<DatasetIcon />} iconPosition="start" label={`Datasets (${datasets?.length || 0})`} />
                <Tab icon={<RequirementIcon />} iconPosition="start" label={`Requirements (${savedRequirements.length})`} />
                <Tab icon={<ValidationIcon />} iconPosition="start" label="Validations" />
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

            {/* Requirements Tab */}
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
                                {savedRequirements.map((req: any) => (
                                    <TableRow key={req.id} hover>
                                        <TableCell>
                                            <Typography variant="body2" fontWeight={500}>{req.name}</Typography>
                                            {req.description && (
                                                <Typography variant="caption" color="text.secondary">{req.description}</Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Chip label={req.principle} size="small" />
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
                                            <Button
                                                size="small"
                                                onClick={() => navigate(`/projects/${id}/requirements/elicit`)}
                                            >
                                                Manage
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </TabPanel>

            {/* Validations Tab */}
            <TabPanel value={tab} index={3}>
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
                            <Typography variant="h6">Validation History</Typography>
                            <Button
                                variant="contained"
                                startIcon={<RunIcon />}
                                onClick={() => navigate(`/projects/${id}/validate`)}
                            >
                                Run New Validation
                            </Button>
                        </Box>
                        
                        <TableContainer component={Card}>
                            <Table>
                                <TableHead>
                                    <TableRow>
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
                                        <TableRow key={validation.suite_id}>
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
                    </>
                )}
            </TabPanel>

            {/* Upload Model Dialog */}
            <Dialog open={uploadModelOpen} onClose={() => setUploadModelOpen(false)} maxWidth="sm" fullWidth>
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
                        onFileSelect={handleModelUpload}
                        uploading={uploading}
                        progress={uploadProgress}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setUploadModelOpen(false)}>Cancel</Button>
                </DialogActions>
            </Dialog>

            {/* Upload Dataset Dialog */}
            <Dialog open={uploadDatasetOpen} onClose={() => setUploadDatasetOpen(false)} maxWidth="sm" fullWidth>
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
                        Supported format: CSV
                    </Typography>

                    <FileUploadArea
                        accept=".csv"
                        onFileSelect={handleDatasetUpload}
                        uploading={uploading}
                        progress={uploadProgress}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setUploadDatasetOpen(false)}>Cancel</Button>
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
