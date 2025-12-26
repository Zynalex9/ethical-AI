// Validation page - Run fairness/transparency/privacy validations

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Box,
    Container,
    Typography,
    Button,
    Card,
    CardContent,
    Grid,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Stepper,
    Step,
    StepLabel,
    Alert,
    CircularProgress,
    Chip,
    IconButton,
} from '@mui/material';
import {
    ArrowBack as BackIcon,
    Balance as FairnessIcon,
    Visibility as TransparencyIcon,
    Lock as PrivacyIcon,
    CheckCircle as CheckIcon,
    Cancel as FailIcon,
    PlayArrow as RunIcon,
} from '@mui/icons-material';
import { useQuery, useMutation } from '@tanstack/react-query';
import { modelsApi, datasetsApi, validationApi } from '../services/api';

const steps = ['Select Model & Dataset', 'Choose Validation Type', 'Configure & Run'];

export default function ValidationPage() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();

    const [activeStep, setActiveStep] = useState(0);
    const [selectedModel, setSelectedModel] = useState('');
    const [selectedDataset, setSelectedDataset] = useState('');
    const [validationType, setValidationType] = useState<'fairness' | 'transparency' | 'privacy'>('fairness');
    const [sensitiveFeature, setSensitiveFeature] = useState('');
    const [targetColumn, setTargetColumn] = useState('');
    const [results, setResults] = useState<any>(null);
    const [error, setError] = useState('');

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

    // Validation mutations
    const fairnessMutation = useMutation({
        mutationFn: () => validationApi.runFairness(selectedModel, selectedDataset, 'req-1'),
        onSuccess: (data) => {
            setResults(data);
            setActiveStep(3);
        },
        onError: (err: Error) => {
            setError(err.message);
        },
    });

    const transparencyMutation = useMutation({
        mutationFn: () => validationApi.runTransparency(selectedModel, selectedDataset),
        onSuccess: (data) => {
            setResults(data);
            setActiveStep(3);
        },
        onError: (err: Error) => {
            setError(err.message);
        },
    });

    const privacyMutation = useMutation({
        mutationFn: () => validationApi.runPrivacy(selectedDataset, {}),
        onSuccess: (data) => {
            setResults(data);
            setActiveStep(3);
        },
        onError: (err: Error) => {
            setError(err.message);
        },
    });

    const handleNext = () => {
        if (activeStep === 0) {
            if (!selectedModel || !selectedDataset) {
                setError('Please select both a model and dataset');
                return;
            }
        }
        setError('');
        setActiveStep((prev) => prev + 1);
    };

    const handleBack = () => {
        setActiveStep((prev) => prev - 1);
    };

    const handleRunValidation = () => {
        setError('');
        if (validationType === 'fairness') {
            if (!sensitiveFeature || !targetColumn) {
                setError('Please specify sensitive feature and target column');
                return;
            }
            fairnessMutation.mutate();
        } else if (validationType === 'transparency') {
            if (!targetColumn) {
                setError('Please specify target column');
                return;
            }
            transparencyMutation.mutate();
        } else {
            privacyMutation.mutate();
        }
    };

    const isRunning = fairnessMutation.isPending || transparencyMutation.isPending || privacyMutation.isPending;

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 4 }}>
                <IconButton onClick={() => navigate(`/projects/${id}`)} sx={{ mr: 2 }}>
                    <BackIcon />
                </IconButton>
                <Typography variant="h4" sx={{ fontWeight: 700 }}>
                    Run Validation
                </Typography>
            </Box>

            {/* Stepper */}
            <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
                {steps.map((label) => (
                    <Step key={label}>
                        <StepLabel>{label}</StepLabel>
                    </Step>
                ))}
                <Step>
                    <StepLabel>Results</StepLabel>
                </Step>
            </Stepper>

            {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                    {error}
                </Alert>
            )}

            {/* Step 1: Select Model & Dataset */}
            {activeStep === 0 && (
                <Card>
                    <CardContent sx={{ p: 4 }}>
                        <Typography variant="h6" gutterBottom>
                            Select Model and Dataset
                        </Typography>
                        <Grid container spacing={3}>
                            <Grid size={{ xs: 12, md: 6 }}>
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
                            </Grid>
                            <Grid size={{ xs: 12, md: 6 }}>
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
                            </Grid>
                        </Grid>
                        <Box sx={{ mt: 4, display: 'flex', justifyContent: 'flex-end' }}>
                            <Button variant="contained" onClick={handleNext}>
                                Next
                            </Button>
                        </Box>
                    </CardContent>
                </Card>
            )}

            {/* Step 2: Choose Validation Type */}
            {activeStep === 1 && (
                <Grid container spacing={3}>
                    {[
                        {
                            type: 'fairness',
                            icon: FairnessIcon,
                            title: 'Fairness Validation',
                            description: 'Check for bias across demographic groups using Fairlearn metrics',
                            color: '#4caf50',
                        },
                        {
                            type: 'transparency',
                            icon: TransparencyIcon,
                            title: 'Transparency Validation',
                            description: 'Generate SHAP explanations and model documentation',
                            color: '#2196f3',
                        },
                        {
                            type: 'privacy',
                            icon: PrivacyIcon,
                            title: 'Privacy Validation',
                            description: 'Detect PII and check k-anonymity of dataset',
                            color: '#ff9800',
                        },
                    ].map((option) => (
                        <Grid key={option.type} size={{ xs: 12, md: 4 }}>
                            <Card
                                sx={{
                                    cursor: 'pointer',
                                    border: validationType === option.type ? 2 : 1,
                                    borderColor: validationType === option.type ? option.color : 'divider',
                                    transition: 'all 0.2s',
                                    '&:hover': {
                                        borderColor: option.color,
                                    },
                                }}
                                onClick={() => setValidationType(option.type as any)}
                            >
                                <CardContent sx={{ textAlign: 'center', py: 4 }}>
                                    <option.icon sx={{ fontSize: 48, color: option.color, mb: 2 }} />
                                    <Typography variant="h6" gutterBottom>
                                        {option.title}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        {option.description}
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>
                    ))}
                    <Grid size={{ xs: 12 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Button onClick={handleBack}>Back</Button>
                            <Button variant="contained" onClick={handleNext}>
                                Next
                            </Button>
                        </Box>
                    </Grid>
                </Grid>
            )}

            {/* Step 3: Configure & Run */}
            {activeStep === 2 && (
                <Card>
                    <CardContent sx={{ p: 4 }}>
                        <Typography variant="h6" gutterBottom>
                            Configure {validationType.charAt(0).toUpperCase() + validationType.slice(1)} Validation
                        </Typography>

                        {validationType === 'fairness' && (
                            <Grid container spacing={3}>
                                <Grid size={{ xs: 12, md: 6 }}>
                                    <FormControl fullWidth>
                                        <InputLabel>Sensitive Feature</InputLabel>
                                        <Select
                                            value={sensitiveFeature}
                                            label="Sensitive Feature"
                                            onChange={(e) => setSensitiveFeature(e.target.value)}
                                        >
                                            {selectedDatasetObj?.columns?.map((col: string) => (
                                                <MenuItem key={col} value={col}>{col}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid size={{ xs: 12, md: 6 }}>
                                    <FormControl fullWidth>
                                        <InputLabel>Target Column</InputLabel>
                                        <Select
                                            value={targetColumn}
                                            label="Target Column"
                                            onChange={(e) => setTargetColumn(e.target.value)}
                                        >
                                            {selectedDatasetObj?.columns?.map((col: string) => (
                                                <MenuItem key={col} value={col}>{col}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                            </Grid>
                        )}

                        {validationType === 'transparency' && (
                            <FormControl fullWidth sx={{ maxWidth: 400 }}>
                                <InputLabel>Target Column</InputLabel>
                                <Select
                                    value={targetColumn}
                                    label="Target Column"
                                    onChange={(e) => setTargetColumn(e.target.value)}
                                >
                                    {selectedDatasetObj?.columns?.map((col: string) => (
                                        <MenuItem key={col} value={col}>{col}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        )}

                        {validationType === 'privacy' && (
                            <Typography color="text.secondary">
                                Privacy validation will automatically detect PII and check data anonymization.
                                No additional configuration required.
                            </Typography>
                        )}

                        <Box sx={{ mt: 4, display: 'flex', justifyContent: 'space-between' }}>
                            <Button onClick={handleBack}>Back</Button>
                            <Button
                                variant="contained"
                                startIcon={isRunning ? <CircularProgress size={20} /> : <RunIcon />}
                                onClick={handleRunValidation}
                                disabled={isRunning}
                            >
                                {isRunning ? 'Running...' : 'Run Validation'}
                            </Button>
                        </Box>
                    </CardContent>
                </Card>
            )}

            {/* Step 4: Results */}
            {activeStep === 3 && results && (
                <Box>
                    <Alert
                        severity={results.overall_passed ? 'success' : 'warning'}
                        sx={{ mb: 3 }}
                        icon={results.overall_passed ? <CheckIcon /> : <FailIcon />}
                    >
                        <Typography variant="h6">
                            Validation {results.overall_passed ? 'Passed' : 'Failed'}
                        </Typography>
                    </Alert>

                    {validationType === 'fairness' && results.metrics && (
                        <Card sx={{ mb: 3 }}>
                            <CardContent>
                                <Typography variant="h6" gutterBottom>Fairness Metrics</Typography>
                                <Grid container spacing={2}>
                                    {Object.entries(results.metrics).map(([name, data]: [string, any]) => (
                                        <Grid key={name} size={{ xs: 12, md: 4 }}>
                                            <Card variant="outlined">
                                                <CardContent>
                                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                        <Typography variant="subtitle1">{name.replace(/_/g, ' ')}</Typography>
                                                        <Chip
                                                            label={data.passed ? 'Pass' : 'Fail'}
                                                            color={data.passed ? 'success' : 'error'}
                                                            size="small"
                                                        />
                                                    </Box>
                                                    <Typography variant="h4" sx={{ my: 1 }}>
                                                        {typeof data.value === 'number' ? data.value.toFixed(3) : data.value}
                                                    </Typography>
                                                    <Typography variant="body2" color="text.secondary">
                                                        Threshold: {data.threshold}
                                                    </Typography>
                                                </CardContent>
                                            </Card>
                                        </Grid>
                                    ))}
                                </Grid>
                            </CardContent>
                        </Card>
                    )}

                    {validationType === 'transparency' && results.global_importance && (
                        <Card sx={{ mb: 3 }}>
                            <CardContent>
                                <Typography variant="h6" gutterBottom>Feature Importance (SHAP)</Typography>
                                {Object.entries(results.global_importance)
                                    .sort(([, a]: any, [, b]: any) => b - a)
                                    .slice(0, 10)
                                    .map(([feature, importance]: [string, any]) => (
                                        <Box key={feature} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                            <Typography sx={{ width: 150, flexShrink: 0 }}>{feature}</Typography>
                                            <Box sx={{ flex: 1, mx: 2 }}>
                                                <Box
                                                    sx={{
                                                        height: 8,
                                                        borderRadius: 1,
                                                        background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)',
                                                        width: `${(importance / Object.values(results.global_importance as Record<string, number>)[0]) * 100}%`,
                                                    }}
                                                />
                                            </Box>
                                            <Typography variant="body2" color="text.secondary">
                                                {importance.toFixed(4)}
                                            </Typography>
                                        </Box>
                                    ))}
                            </CardContent>
                        </Card>
                    )}

                    {validationType === 'privacy' && (
                        <>
                            {results.pii_detected?.length > 0 && (
                                <Card sx={{ mb: 3 }}>
                                    <CardContent>
                                        <Typography variant="h6" gutterBottom color="warning.main">
                                            ⚠️ PII Detected
                                        </Typography>
                                        {results.pii_detected.map((pii: any, i: number) => (
                                            <Chip
                                                key={i}
                                                label={`${pii.column_name}: ${pii.pii_type}`}
                                                color="warning"
                                                sx={{ mr: 1, mb: 1 }}
                                            />
                                        ))}
                                    </CardContent>
                                </Card>
                            )}

                            {results.recommendations?.length > 0 && (
                                <Card>
                                    <CardContent>
                                        <Typography variant="h6" gutterBottom>Recommendations</Typography>
                                        {results.recommendations.map((rec: string, i: number) => (
                                            <Alert key={i} severity="info" sx={{ mb: 1 }}>
                                                {rec}
                                            </Alert>
                                        ))}
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    )}

                    <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
                        <Button variant="outlined" onClick={() => navigate(`/projects/${id}`)}>
                            Back to Project
                        </Button>
                        <Button variant="contained" onClick={() => setActiveStep(0)}>
                            Run Another Validation
                        </Button>
                    </Box>
                </Box>
            )}
        </Container>
    );
}
