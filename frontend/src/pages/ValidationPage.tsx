import { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
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
    const [searchParams] = useSearchParams();
    const viewSuiteId = searchParams.get('suite');

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

    // Warning dialog state
    const [showWarningDialog, setShowWarningDialog] = useState(false);
    const [pendingSubmit, setPendingSubmit] = useState(false);

    // Load existing validation results if suite ID is provided
    useEffect(() => {
        if (viewSuiteId) {
            loadSuiteResults(viewSuiteId);
        }
    }, [viewSuiteId]);

    const loadSuiteResults = async (suite_id: string) => {
        try {
            const suiteResults = await validationApi.getSuiteResults(suite_id);
            setResults(suiteResults);
            setSuiteId(suite_id);
        } catch (err: any) {
            console.error('Error loading suite results:', err);
            setError(err.message || 'Failed to load validation results');
        }
    };

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
        // If this is the initial click (not from dialog confirmation) and no target column
        if (!pendingSubmit && !targetColumn) {
            setPendingSubmit(true);
            setShowWarningDialog(true);
            return; // Show warning dialog instead of proceeding
        }

        setError('');

        // Validation
        if (!selectedModel || !selectedDataset) {
            setError('Please select both a model and dataset');
            return;
        }
        if (!sensitiveFeature) {
            setError('Please specify sensitive feature');
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
                    target_column: targetColumn || null, // Allow null
                    thresholds: {
                        demographic_parity_ratio: 0.8,
                        equalized_odds_ratio: 0.8,
                        disparate_impact_ratio: 0.8,
                    },
                },
                transparency_config: {
                    target_column: targetColumn || null, // Allow null
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
        <>
            {/* Warning Dialog for Missing Target Column */}
            <Dialog
                open={showWarningDialog}
                onClose={() => {
                    setShowWarningDialog(false);
                    setPendingSubmit(false);
                }}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle sx={{ bgcolor: 'warning.main', color: 'warning.contrastText' }}>
                    ⚠️ Warning: No Target Column Specified
                </DialogTitle>
                <DialogContent sx={{ mt: 2 }}>
                    <DialogContentText>
                        You have not specified a target column (ground truth). The validation will proceed using <strong>model predictions as the ground truth</strong>.
                    </DialogContentText>
                    <DialogContentText sx={{ mt: 2, fontWeight: 600 }}>
                        This means:
                    </DialogContentText>
                    <Box component="ul" sx={{ mt: 1, pl: 2 }}>
                        <Box component="li" sx={{ mb: 1 }}>
                            <DialogContentText>
                                The fairness analysis will check if the model's predictions are <strong>internally consistent</strong> across groups
                            </DialogContentText>
                        </Box>
                        <Box component="li" sx={{ mb: 1 }}>
                            <DialogContentText>
                                It will NOT compare predictions to actual outcomes
                            </DialogContentText>
                        </Box>
                        <Box component="li" sx={{ mb: 1 }}>
                            <DialogContentText>
                                Results may be <strong>inaccurate or misleading</strong> without ground truth
                            </DialogContentText>
                        </Box>
                    </Box>
                    <DialogContentText sx={{ mt: 2, color: 'error.main', fontWeight: 600 }}>
                        Are you sure you want to proceed without providing the target column?
                    </DialogContentText>
                </DialogContent>
                <DialogActions sx={{ p: 2 }}>
                    <Button
                        onClick={() => {
                            setShowWarningDialog(false);
                            setPendingSubmit(false);
                        }}
                        variant="outlined"
                    >
                        Cancel - Add Target Column
                    </Button>
                    <Button
                        onClick={() => {
                            setShowWarningDialog(false);
                            setPendingSubmit(false);
                            handleRunAllValidations();
                        }}
                        variant="contained"
                        color="warning"
                    >
                        Proceed Without Target
                    </Button>
                </DialogActions>
            </Dialog>

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
                                            <InputLabel>Target Column (Optional)</InputLabel>
                                            <Select
                                                value={targetColumn}
                                                label="Target Column (Optional)"
                                                onChange={(e) => setTargetColumn(e.target.value)}
                                                disabled={!selectedDataset}
                                            >
                                                <MenuItem value="">
                                                    <em>None - Use model predictions</em>
                                                </MenuItem>
                                                {selectedDatasetObj?.columns?.map((col: string) => (
                                                    <MenuItem key={col} value={col}>{col}</MenuItem>
                                                ))}
                                            </Select>
                                            {!targetColumn && (
                                                <Typography variant="caption" color="warning.main" sx={{ mt: 0.5, ml: 1 }}>
                                                    ⚠️ Without target column, fairness will be checked using model predictions
                                                </Typography>
                                            )}
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
                                    disabled={!selectedModel || !selectedDataset || !sensitiveFeature}
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
                                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                                Progress: {results.validations.fairness.progress}%
                                            </Typography>

                                            {/* Display detailed metrics if available */}
                                            {results.validations.fairness.results && results.validations.fairness.results.length > 0 && (
                                                <Box sx={{ mt: 2 }}>
                                                    <Typography variant="subtitle2" sx={{ mb: 1 }}>Metrics:</Typography>
                                                    {results.validations.fairness.results.map((metric: any, idx: number) => (
                                                        <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                                            <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                                                                {metric.metric_name.replace(/_/g, ' ')}
                                                            </Typography>
                                                            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                                                                <Typography variant="caption" color="text.secondary">
                                                                    {metric.metric_value?.toFixed(3)} / {metric.threshold}
                                                                </Typography>
                                                                <Chip
                                                                    label={metric.passed ? '✓' : '✗'}
                                                                    color={metric.passed ? 'success' : 'error'}
                                                                    size="small"
                                                                    sx={{ minWidth: 30, height: 20 }}
                                                                />
                                                            </Box>
                                                        </Box>
                                                    ))}
                                                </Box>
                                            )}

                                            {results.validations.fairness.mlflow_run_id && (
                                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
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
                                            
                                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                                Progress: 100%
                                            </Typography>

                                            {/* Feature Importance */}
                                            {results.validations.transparency.global_importance && (
                                                <Box sx={{ mt: 2 }}>
                                                    <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                                                        Top Feature Importances:
                                                    </Typography>
                                                    {Object.entries(results.validations.transparency.global_importance)
                                                        .sort(([, a]: any, [, b]: any) => b - a)
                                                        .slice(0, 5)
                                                        .map(([feature, importance]: any) => (
                                                            <Box key={feature} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                                                <Typography variant="caption">{feature}:</Typography>
                                                                <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
                                                                    {(importance * 100).toFixed(2)}%
                                                                </Typography>
                                                            </Box>
                                                        ))}
                                                </Box>
                                            )}

                                            {/* Model Card Metrics */}
                                            {results.validations.transparency.model_card?.performance_metrics && (
                                                <Box sx={{ mt: 2 }}>
                                                    <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                                                        Model Performance:
                                                    </Typography>
                                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                                                        {Object.entries(results.validations.transparency.model_card.performance_metrics).map(([metric, value]: any) => (
                                                            <Chip
                                                                key={metric}
                                                                label={`${metric}: ${(value * 100).toFixed(1)}%`}
                                                                size="small"
                                                                variant="outlined"
                                                            />
                                                        ))}
                                                    </Box>
                                                </Box>
                                            )}

                                            {results.validations.transparency.mlflow_run_id && (
                                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                                                    MLflow Run: {results.validations.transparency.mlflow_run_id.substring(0, 8)}...
                                                </Typography>
                                            )}

                                            <Button
                                                variant="outlined"
                                                color="primary"
                                                fullWidth
                                                sx={{ mt: 2 }}
                                                onClick={() => navigate(`/validations/${results.suite_id}/transparency`)}
                                            >
                                                View Detailed Transparency Report
                                            </Button>
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
                                            
                                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                                Progress: 100%
                                            </Typography>

                                            {/* PII Detection */}
                                            {results.validations.privacy.pii_detected && (
                                                <Box sx={{ mt: 2 }}>
                                                    <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                                                        PII Detection:
                                                    </Typography>
                                                    <Typography variant="body2" color={results.validations.privacy.pii_detected.length > 0 ? 'error' : 'success'}>
                                                        {results.validations.privacy.pii_detected.length > 0 
                                                            ? `⚠️ ${results.validations.privacy.pii_detected.length} column(s) with PII detected`
                                                            : '✓ No PII detected'}
                                                    </Typography>
                                                    {results.validations.privacy.pii_detected.length > 0 && (
                                                        <Box sx={{ mt: 1, pl: 2 }}>
                                                            {results.validations.privacy.pii_detected.map((pii: any, idx: number) => (
                                                                <Typography key={idx} variant="caption" sx={{ display: 'block' }}>
                                                                    • {pii.column_name}: {pii.pii_type} ({(pii.confidence * 100).toFixed(0)}%)
                                                                </Typography>
                                                            ))}
                                                        </Box>
                                                    )}
                                                </Box>
                                            )}

                                            {/* k-Anonymity */}
                                            {results.validations.privacy.k_anonymity && (
                                                <Box sx={{ mt: 2 }}>
                                                    <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                                                        k-Anonymity (k={results.validations.privacy.k_anonymity.k_value}):
                                                    </Typography>
                                                    <Chip
                                                        label={results.validations.privacy.k_anonymity.satisfies_k ? 'PASSED' : 'FAILED'}
                                                        color={results.validations.privacy.k_anonymity.satisfies_k ? 'success' : 'error'}
                                                        size="small"
                                                        sx={{ mb: 1 }}
                                                    />
                                                    {!results.validations.privacy.k_anonymity.satisfies_k && (
                                                        <Typography variant="caption" sx={{ display: 'block' }}>
                                                            Min group size: {results.validations.privacy.k_anonymity.actual_min_k}<br />
                                                            Violating groups: {results.validations.privacy.k_anonymity.violating_groups_count}
                                                        </Typography>
                                                    )}
                                                </Box>
                                            )}

                                            {/* l-Diversity */}
                                            {results.validations.privacy.l_diversity && (
                                                <Box sx={{ mt: 2 }}>
                                                    <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                                                        l-Diversity (l={results.validations.privacy.l_diversity.l_value}):
                                                    </Typography>
                                                    <Chip
                                                        label={results.validations.privacy.l_diversity.satisfies_l ? 'PASSED' : 'FAILED'}
                                                        color={results.validations.privacy.l_diversity.satisfies_l ? 'success' : 'error'}
                                                        size="small"
                                                        sx={{ mb: 1 }}
                                                    />
                                                    {!results.validations.privacy.l_diversity.satisfies_l && (
                                                        <Typography variant="caption" sx={{ display: 'block' }}>
                                                            Sensitive: {results.validations.privacy.l_diversity.sensitive_attribute}<br />
                                                            Violating groups: {results.validations.privacy.l_diversity.violating_groups_count}
                                                        </Typography>
                                                    )}
                                                </Box>
                                            )}

                                            {/* Overall Status */}
                                            <Box sx={{ mt: 2, p: 1, bgcolor: results.validations.privacy.overall_passed ? 'success.light' : 'error.light', borderRadius: 1 }}>
                                                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                                                    {results.validations.privacy.overall_passed ? '✓ Privacy Validated' : '⚠️ Privacy Issues Found'}
                                                </Typography>
                                            </Box>

                                            {results.validations.privacy.mlflow_run_id && (
                                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                                                    MLflow Run: {results.validations.privacy.mlflow_run_id.substring(0, 8)}...
                                                </Typography>
                                            )}

                                            <Button
                                                variant="outlined"
                                                color="primary"
                                                fullWidth
                                                sx={{ mt: 2 }}
                                                onClick={() => navigate(`/validations/${results.suite_id}/privacy`)}
                                            >
                                                View Detailed Privacy Report
                                            </Button>
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
        </>
    );
}
