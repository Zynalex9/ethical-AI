import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
} from '@mui/material';
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
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { modelsApi, datasetsApi, validationApi } from '../services/api';

export default function ValidationPage() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();

    // Form state
    const [selectedModel, setSelectedModel] = useState('');
    const [selectedDataset, setSelectedDataset] = useState('');
    const [sensitiveFeature, setSensitiveFeature] = useState('');
    const [targetColumn, setTargetColumn] = useState('');
    const [quasiIdentifiers, setQuasiIdentifiers] = useState<string[]>([]);
    const [sensitiveAttribute, setSensitiveAttribute] = useState('');
    const [error, setError] = useState('');

    // Validation state
    const [isRunning, setIsRunning] = useState(false);
    const [taskId, setTaskId] = useState('');
    const [suiteId, setSuiteId] = useState('');
    const [progress, setProgress] = useState(0);
    const [currentStep, setCurrentStep] = useState('');
    const [results, setResults] = useState<any>(null);

    // Fetch models and datasets
    const { data: models } = useQuery({
        queryKey: ['models', id],
        queryFn: () => modelsApi.list(id!),
        enabled: !!id,
    });

    const { data: datasets } = useQuery({
        queryKey: ['datasets', id],
        queryFn: () => datasetsApi.list(id!),
        enabled: !!id,
    });

    // Get selected dataset for column info
    const selectedDatasetObj = datasets?.find((d: any) => d.id === selectedDataset);

    // Poll task status
    useEffect(() => {
        if (!taskId || !isRunning) return;

        const interval = setInterval(async () => {
            try {
                const status = await validationApi.getTaskStatus(taskId);

                setProgress(status.progress);
                setCurrentStep(status.current_step || '');

                if (status.state === 'SUCCESS') {
                    // Task completed, fetch results
                    if (suiteId) {
                        const suiteResults = await validationApi.getSuiteResults(suiteId);
                        setResults(suiteResults);
                    }
                    setIsRunning(false);
                    clearInterval(interval);
                } else if (status.state === 'FAILURE') {
                    setError(status.error || 'Validation failed');
                    setIsRunning(false);
                    clearInterval(interval);
                }
            } catch (err: any) {
                console.error('Error polling status:', err);
                setError(err.message);
                setIsRunning(false);
                clearInterval(interval);
            }
        }, 2000); // Poll every 2 seconds

        return () => clearInterval(interval);
    }, [taskId, isRunning, suiteId]);

    const handleRunAllValidations = async () => {
        setError('');

        // Validation
        if (!selectedModel || !selectedDataset) {
            setError('Please select both a model and dataset');
            return;
        }
        if (!sensitiveFeature || !targetColumn) {
            setError('Please specify sensitive feature and target column');
            return;
        }

        setIsRunning(true);
        setProgress(0);
        setCurrentStep('Queuing validations...');
        setResults(null);

        try {
            const response = await validationApi.runAll({
                model_id: selectedModel,
                dataset_id: selectedDataset,
                fairness_config: {
                    sensitive_feature: sensitiveFeature,
                    target_column: targetColumn,
                    thresholds: {
                        demographic_parity_ratio: 0.8,
                        equalized_odds_ratio: 0.8,
                        disparate_impact_ratio: 0.8,
                    },
                },
                transparency_config: {
                    target_column: targetColumn,
                    sample_size: 100,
                },
                privacy_config: {
                    k_anonymity_k: 5,
                    l_diversity_l: 2,
                    quasi_identifiers: quasiIdentifiers.length > 0 ? quasiIdentifiers : undefined,
                    sensitive_attribute: sensitiveAttribute || undefined,
                },
            });

            setTaskId(response.task_id);
            setSuiteId(response.suite_id);
            setCurrentStep('Validation suite queued');
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message);
            setIsRunning(false);
        }
    };

    const handleReset = () => {
        setIsRunning(false);
        setTaskId('');
        setSuiteId('');
        setProgress(0);
        setCurrentStep('');
        setResults(null);
        setError('');
    };

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 4 }}>
                <IconButton onClick={() => navigate(`/projects/${id}`)} sx={{ mr: 2 }}>
                    <BackIcon />
                </IconButton>
                <Typography variant="h4" sx={{ fontWeight: 700 }}>
                    Ethical AI Validation Suite
                </Typography>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
                    {error}
                </Alert>
            )}

            {/* Configuration Form */}
            {!isRunning && !results && (
                <Card sx={{ mb: 3 }}>
                    <CardContent sx={{ p: 4 }}>
                        <Typography variant="h6" gutterBottom>
                            Configure Validation Suite
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                            This will run all 4 ethical validations: Fairness, Transparency, Privacy, and Accountability
                        </Typography>

                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                            {/* Row 1 */}
                            <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                                {/* Model Selection */}
                                <Box sx={{ flex: '1 1 45%', minWidth: 250 }}>
                                    <FormControl fullWidth>
                                        <InputLabel>Model</InputLabel>
                                        <Select
                                            value={selectedModel}
                                            label="Model"
                                            onChange={(e) => setSelectedModel(e.target.value)}
                                        >
                                            {models?.map((model: any) => (
                                                <MenuItem key={model.id} value={model.id}>
                                                    {model.name} ({model.model_type})
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>

                                {/* Dataset Selection */}
                                <Box sx={{ flex: '1 1 45%', minWidth: 250 }}>
                                    <FormControl fullWidth>
                                        <InputLabel>Dataset</InputLabel>
                                        <Select
                                            value={selectedDataset}
                                            label="Dataset"
                                            onChange={(e) => setSelectedDataset(e.target.value)}
                                        >
                                            {datasets?.map((dataset: any) => (
                                                <MenuItem key={dataset.id} value={dataset.id}>
                                                    {dataset.name} ({dataset.row_count} rows)
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>
                            </Box>

                            {/* Row 2 */}
                            <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                                {/* Sensitive Feature */}
                                <Box sx={{ flex: '1 1 45%', minWidth: 250 }}>
                                    <FormControl fullWidth>
                                        <InputLabel>Sensitive Feature (for Fairness)</InputLabel>
                                        <Select
                                            value={sensitiveFeature}
                                            label="Sensitive Feature (for Fairness)"
                                            onChange={(e) => setSensitiveFeature(e.target.value)}
                                            disabled={!selectedDataset}
                                        >
                                            {selectedDatasetObj?.columns?.map((col: string) => (
                                                <MenuItem key={col} value={col}>{col}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>

                                {/* Target Column */}
                                <Box sx={{ flex: '1 1 45%', minWidth: 250 }}>
                                    <FormControl fullWidth>
                                        <InputLabel>Target Column</InputLabel>
                                        <Select
                                            value={targetColumn}
                                            label="Target Column"
                                            onChange={(e) => setTargetColumn(e.target.value)}
                                            disabled={!selectedDataset}
                                        >
                                            {selectedDatasetObj?.columns?.map((col: string) => (
                                                <MenuItem key={col} value={col}>{col}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>
                            </Box>

                            {/* Row 3 */}
                            <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                                {/* Quasi Identifiers */}
                                <Box sx={{ flex: '1 1 45%', minWidth: 250 }}>
                                    <FormControl fullWidth>
                                        <InputLabel>Quasi-Identifiers (Optional, for Privacy)</InputLabel>
                                        <Select
                                            multiple
                                            value={quasiIdentifiers}
                                            label="Quasi-Identifiers (Optional, for Privacy)"
                                            onChange={(e) => setQuasiIdentifiers(e.target.value as string[])}
                                            disabled={!selectedDataset}
                                            renderValue={(selected) => (
                                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                                    {selected.map((value) => (
                                                        <Chip key={value} label={value} size="small" />
                                                    ))}
                                                </Box>
                                            )}
                                        >
                                            {selectedDatasetObj?.columns?.map((col: string) => (
                                                <MenuItem key={col} value={col}>{col}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>

                                {/* Sensitive Attribute */}
                                <Box sx={{ flex: '1 1 45%', minWidth: 250 }}>
                                    <FormControl fullWidth>
                                        <InputLabel>Sensitive Attribute (Optional, for Privacy)</InputLabel>
                                        <Select
                                            value={sensitiveAttribute}
                                            label="Sensitive Attribute (Optional, for Privacy)"
                                            onChange={(e) => setSensitiveAttribute(e.target.value)}
                                            disabled={!selectedDataset}
                                        >
                                            <MenuItem value="">None</MenuItem>
                                            {selectedDatasetObj?.columns?.map((col: string) => (
                                                <MenuItem key={col} value={col}>{col}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>
                            </Box>
                        </Box>

                        <Box sx={{ mt: 4, display: 'flex', justifyContent: 'flex-end' }}>
                            <Button
                                variant="contained"
                                size="large"
                                startIcon={<RunIcon />}
                                onClick={handleRunAllValidations}
                                disabled={!selectedModel || !selectedDataset || !sensitiveFeature || !targetColumn}
                            >
                                Run All Validations
                            </Button>
                        </Box>
                    </CardContent>
                </Card>
            )}

            {/* Progress Indicator */}
            {isRunning && (
                <Paper sx={{ p: 4, mb: 3 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <CircularProgress size={24} sx={{ mr: 2 }} />
                        <Typography variant="h6">Running Validations...</Typography>
                    </Box>
                    <LinearProgress variant="determinate" value={progress} sx={{ mb: 2, height: 8, borderRadius: 1 }} />
                    <Typography variant="body2" color="text.secondary">
                        {currentStep} ({progress}%)
                    </Typography>
                </Paper>
            )}

            {/* Results */}
            {results && (
                <Box>
                    <Alert
                        severity={results.overall_passed ? 'success' : 'warning'}
                        sx={{ mb: 3 }}
                        icon={results.overall_passed ? <CheckIcon /> : <FailIcon />}
                    >
                        <Typography variant="h6">
                            Validation Suite {results.overall_passed ? 'Passed' : 'Failed'}
                        </Typography>
                        <Typography variant="body2">
                            Suite ID: {results.suite_id}
                        </Typography>
                    </Alert>

                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                        {results.validations?.fairness && (
                            <Box sx={{ flex: '1 1 45%', minWidth: 300 }}>
                                <Card>
                                    <CardContent>
                                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                            <FairnessIcon sx={{ fontSize: 32, color: '#4caf50', mr: 2 }} />
                                            <Box sx={{ flex: 1 }}>
                                                <Typography variant="h6">Fairness Validation</Typography>
                                                <Chip
                                                    label={results.validations.fairness.status}
                                                    color={results.validations.fairness.status === 'completed' ? 'success' : 'default'}
                                                    size="small"
                                                />
                                            </Box>
                                        </Box>
                                        <Typography variant="body2" color="text.secondary">
                                            Progress: {results.validations.fairness.progress}%
                                        </Typography>
                                        {results.validations.fairness.mlflow_run_id && (
                                            <Typography variant="caption" color="text.secondary">
                                                MLflow Run: {results.validations.fairness.mlflow_run_id.substring(0, 8)}...
                                            </Typography>
                                        )}
                                    </CardContent>
                                </Card>
                            </Box>
                        )}

                        {results.validations?.transparency && (
                            <Box sx={{ flex: '1 1 45%', minWidth: 300 }}>
                                <Card>
                                    <CardContent>
                                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                            <TransparencyIcon sx={{ fontSize: 32, color: '#2196f3', mr: 2 }} />
                                            <Box sx={{ flex: 1 }}>
                                                <Typography variant="h6">Transparency Validation</Typography>
                                                <Chip
                                                    label={results.validations.transparency.status}
                                                    color={results.validations.transparency.status === 'completed' ? 'success' : 'default'}
                                                    size="small"
                                                />
                                            </Box>
                                        </Box>
                                        <Typography variant="body2" color="text.secondary">
                                            Progress: {results.validations.transparency.progress}%
                                        </Typography>
                                        {results.validations.transparency.mlflow_run_id && (
                                            <Typography variant="caption" color="text.secondary">
                                                MLflow Run: {results.validations.transparency.mlflow_run_id.substring(0, 8)}...
                                            </Typography>
                                        )}
                                    </CardContent>
                                </Card>
                            </Box>
                        )}

                        {results.validations?.privacy && (
                            <Box sx={{ flex: '1 1 45%', minWidth: 300 }}>
                                <Card>
                                    <CardContent>
                                        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                            <PrivacyIcon sx={{ fontSize: 32, color: '#ff9800', mr: 2 }} />
                                            <Box sx={{ flex: 1 }}>
                                                <Typography variant="h6">Privacy Validation</Typography>
                                                <Chip
                                                    label={results.validations.privacy.status}
                                                    color={results.validations.privacy.status === 'completed' ? 'success' : 'default'}
                                                    size="small"
                                                />
                                            </Box>
                                        </Box>
                                        <Typography variant="body2" color="text.secondary">
                                            Progress: {results.validations.privacy.progress}%
                                        </Typography>
                                        {results.validations.privacy.mlflow_run_id && (
                                            <Typography variant="caption" color="text.secondary">
                                                MLflow Run: {results.validations.privacy.mlflow_run_id.substring(0, 8)}...
                                            </Typography>
                                        )}
                                    </CardContent>
                                </Card>
                            </Box>
                        )}

                        {/* Accountability */}
                        <Box sx={{ flex: '1 1 45%', minWidth: 300 }}>
                            <Card>
                                <CardContent>
                                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                        <AccountabilityIcon sx={{ fontSize: 32, color: '#9c27b0', mr: 2 }} />
                                        <Box sx={{ flex: 1 }}>
                                            <Typography variant="h6">Accountability Tracking</Typography>
                                            <Chip
                                                label="MLflow Integrated"
                                                color="success"
                                                size="small"
                                            />
                                        </Box>
                                    </Box>
                                    <Typography variant="body2" color="text.secondary">
                                        All validations tracked in MLflow
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        View experiment runs in MLflow UI
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Box>
                    </Box>

                    <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
                        <Button variant="outlined" onClick={() => navigate(`/projects/${id}`)}>
                            Back to Project
                        </Button>
                        <Button variant="contained" startIcon={<RefreshIcon />} onClick={handleReset}>
                            Run Another Validation
                        </Button>
                    </Box>
                </Box>
            )}
        </Container>
    );
}
