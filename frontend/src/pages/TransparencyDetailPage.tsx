import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
    Box,
    Button,
    Card,
    CardContent,
    Typography,
    CircularProgress,
    Alert,
    Chip,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    LinearProgress,
} from '@mui/material';
import {
    ArrowBack,
    Visibility,
    TrendingUp,
    Assessment,
    Info,
} from '@mui/icons-material';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { validationApi } from '../services/api';

interface FeatureImportance {
    [feature: string]: number;
}

interface ModelCard {
    model_details: {
        name: string;
        description?: string;
        model_type: string;
        n_features: number;
        feature_names?: string[];
    };
    intended_use?: {
        primary_use: string;
        users?: string;
    };
    performance_metrics: {
        accuracy: number;
        precision: number;
        recall: number;
        f1_score: number;
    };
    additional_info?: any;
}

interface TransparencyData {
    validation_id: string;
    status: string;
    mlflow_run_id: string;
    feature_importance: FeatureImportance;
    model_card: ModelCard;
    sample_predictions: Array<{
        sample_index: number;
        true_label: number;
        predicted_label: number;
        correct: boolean;
        top_features: Record<string, {
            value: number;
            shap_contribution: number;
        }>;
        base_value: number;
    }>;
    completed_at: string;
}

export default function TransparencyDetailPage() {
    const { validationId } = useParams<{ validationId: string }>();
    const navigate = useNavigate();

    const { data: transparencyData, isLoading, error } = useQuery<TransparencyData>({
        queryKey: ['transparencyDetails', validationId],
        queryFn: () => validationApi.getTransparencyDetails(validationId!),
        enabled: !!validationId,
        retry: 1,
    });

    if (isLoading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress />
            </Box>
        );
    }

    if (error || !transparencyData) {
        return (
            <Box p={3}>
                <Alert severity="error">
                    Failed to load transparency details: {error instanceof Error ? error.message : 'Unknown error'}
                </Alert>
                <Button startIcon={<ArrowBack />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
                    Go Back
                </Button>
            </Box>
        );
    }

    // Check if we have the required data
    const hasFeatureImportance = transparencyData.feature_importance && Object.keys(transparencyData.feature_importance).length > 0;
    const hasModelCard = transparencyData.model_card && transparencyData.model_card.performance_metrics;

    // Debug: Log sample predictions
    console.log('Sample predictions data:', transparencyData.sample_predictions);
    console.log('Sample predictions length:', transparencyData.sample_predictions?.length);

    if (!hasFeatureImportance && !hasModelCard) {
        return (
            <Box p={3}>
                <Alert severity="warning">
                    No transparency data available yet. The validation may still be processing or no artifacts were generated.
                </Alert>
                <Button startIcon={<ArrowBack />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
                    Go Back
                </Button>
                <Box mt={2}>
                    <Typography variant="caption" color="text.secondary">
                        Debug info: {JSON.stringify(transparencyData, null, 2)}
                    </Typography>
                </Box>
            </Box>
        );
    }

    // Prepare data for chart
    const chartData = hasFeatureImportance 
        ? Object.entries(transparencyData.feature_importance)
            .slice(0, 10) // Top 10 features
            .map(([name, value]) => ({
                name: name.length > 15 ? name.substring(0, 15) + '...' : name,
                importance: Math.abs(value) * 100, // Convert to percentage
                fullName: name,
            }))
        : [];

    // Get top 5 features
    const topFeatures = hasFeatureImportance 
        ? Object.entries(transparencyData.feature_importance).slice(0, 5)
        : [];

    const metrics = hasModelCard ? transparencyData.model_card.performance_metrics : null;

    // Color scale for bars
    const getColor = (index: number) => {
        const colors = ['#1976d2', '#2196f3', '#42a5f5', '#64b5f6', '#90caf9', '#bbdefb'];
        return colors[Math.min(index, colors.length - 1)];
    };

    return (
        <Box sx={{ p: 3, maxWidth: 1400, margin: '0 auto' }}>
            {/* Header */}
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Box display="flex" alignItems="center" gap={2}>
                    <Button
                        startIcon={<ArrowBack />}
                        onClick={() => navigate(-1)}
                        variant="outlined"
                    >
                        Back to Validation
                    </Button>
                    <Box>
                        <Typography variant="h4" gutterBottom>
                            Transparency Analysis
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Model explainability using SHAP feature importance
                        </Typography>
                    </Box>
                </Box>
                <Chip
                    label={transparencyData.status}
                    color="success"
                    icon={<Assessment />}
                />
            </Box>

            {/* Feature Importance Section */}
            {hasFeatureImportance && chartData.length > 0 && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                    <Box display="flex" alignItems="center" gap={1} mb={2}>
                        <TrendingUp color="primary" />
                        <Typography variant="h6">
                            Feature Importance (SHAP Values)
                        </Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary" mb={3}>
                        Shows which features have the most influence on the model's predictions overall.
                        Higher values indicate greater importance.
                    </Typography>

                    {/* Bar Chart */}
                    <ResponsiveContainer width="100%" height={400}>
                        <BarChart data={chartData} layout="vertical" margin={{ left: 100, right: 30 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis type="number" label={{ value: 'Importance (%)', position: 'insideBottom', offset: -5 }} />
                            <YAxis type="category" dataKey="name" />
                            <Tooltip
                                content={({ payload }: any) => {
                                    if (payload && payload[0]) {
                                        const data = payload[0].payload;
                                        return (
                                            <Paper sx={{ p: 1 }}>
                                                <Typography variant="body2">
                                                    <strong>{data.fullName}</strong>
                                                </Typography>
                                                <Typography variant="body2" color="primary">
                                                    Importance: {data.importance.toFixed(2)}%
                                                </Typography>
                                            </Paper>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Bar dataKey="importance" fill="#1976d2">
                                {chartData.map((_entry, index) => (
                                    <Cell key={`cell-${index}`} fill={getColor(index)} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>

                    {/* Feature Importance Table */}
                    <Box mt={4}>
                        <Typography variant="h6" gutterBottom>
                            Feature Rankings
                        </Typography>
                        <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell><strong>Rank</strong></TableCell>
                                        <TableCell><strong>Feature Name</strong></TableCell>
                                        <TableCell align="right"><strong>Importance</strong></TableCell>
                                        <TableCell width="200"><strong>Visual</strong></TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {topFeatures.map(([name, value], index) => {
                                        const percentage = Math.abs(value) * 100;
                                        return (
                                            <TableRow key={name} hover>
                                                <TableCell>{index + 1}</TableCell>
                                                <TableCell>
                                                    <Typography variant="body2" fontWeight="medium">
                                                        {name}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell align="right">
                                                    <Chip
                                                        label={`${percentage.toFixed(2)}%`}
                                                        size="small"
                                                        color="primary"
                                                        variant="outlined"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <LinearProgress
                                                        variant="determinate"
                                                        value={percentage}
                                                        sx={{ height: 8, borderRadius: 1 }}
                                                    />
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Box>
                </CardContent>
            </Card>
            )}

            {/* Model Performance & Model Card Row */}
            {hasModelCard && metrics && (
                <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
                {/* Model Performance */}
                <Box sx={{ flex: '1 1 45%', minWidth: 300 }}>
                    <Card sx={{ height: '100%' }}>
                        <CardContent>
                            <Box display="flex" alignItems="center" gap={1} mb={2}>
                                <Assessment color="success" />
                                <Typography variant="h6">Model Performance</Typography>
                            </Box>

                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                                <Box sx={{ flex: '1 1 45%', minWidth: 120 }}>
                                    <Paper elevation={0} sx={{ p: 2, bgcolor: 'success.lighter', textAlign: 'center' }}>
                                        <Typography variant="h4" color="success.main">
                                            {(metrics.accuracy * 100).toFixed(1)}%
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Accuracy
                                        </Typography>
                                    </Paper>
                                </Box>
                                <Box sx={{ flex: '1 1 45%', minWidth: 120 }}>
                                    <Paper elevation={0} sx={{ p: 2, bgcolor: 'info.lighter', textAlign: 'center' }}>
                                        <Typography variant="h4" color="info.main">
                                            {(metrics.precision * 100).toFixed(1)}%
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Precision
                                        </Typography>
                                    </Paper>
                                </Box>
                                <Box sx={{ flex: '1 1 45%', minWidth: 120 }}>
                                    <Paper elevation={0} sx={{ p: 2, bgcolor: 'warning.lighter', textAlign: 'center' }}>
                                        <Typography variant="h4" color="warning.main">
                                            {(metrics.recall * 100).toFixed(1)}%
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Recall
                                        </Typography>
                                    </Paper>
                                </Box>
                                <Box sx={{ flex: '1 1 45%', minWidth: 120 }}>
                                    <Paper elevation={0} sx={{ p: 2, bgcolor: 'secondary.lighter', textAlign: 'center' }}>
                                        <Typography variant="h4" color="secondary.main">
                                            {(metrics.f1_score * 100).toFixed(1)}%
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            F1-Score
                                        </Typography>
                                    </Paper>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Box>

                {/* Model Card */}
                <Box sx={{ flex: '1 1 45%', minWidth: 300 }}>
                    <Card sx={{ height: '100%' }}>
                        <CardContent>
                            <Box display="flex" alignItems="center" gap={1} mb={2}>
                                <Info color="info" />
                                <Typography variant="h6">Model Card</Typography>
                            </Box>

                            <Box>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                    Model Details
                                </Typography>
                                <Typography variant="body2" gutterBottom>
                                    <strong>Name:</strong> {transparencyData.model_card.model_details.name}
                                </Typography>
                                <Typography variant="body2" gutterBottom>
                                    <strong>Type:</strong> {transparencyData.model_card.model_details.model_type}
                                </Typography>
                                <Typography variant="body2" gutterBottom>
                                    <strong>Features:</strong> {transparencyData.model_card.model_details.n_features}
                                </Typography>

                                {transparencyData.model_card.intended_use && (
                                    <Box mt={2}>
                                        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                            Intended Use
                                        </Typography>
                                        <Typography variant="body2" gutterBottom>
                                            <strong>Primary:</strong> {transparencyData.model_card.intended_use.primary_use}
                                        </Typography>
                                        {transparencyData.model_card.intended_use.users && (
                                            <Typography variant="body2" gutterBottom>
                                                <strong>Users:</strong> {transparencyData.model_card.intended_use.users}
                                            </Typography>
                                        )}
                                    </Box>
                                )}

                                <Box mt={2}>
                                    <Typography variant="caption" color="text.secondary">
                                        MLflow Run: {transparencyData.mlflow_run_id.substring(0, 8)}...
                                    </Typography>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Box>
            </Box>
            )}

            {/* Insights Card */}
            {hasFeatureImportance && topFeatures.length > 0 && (
                <Card>
                <CardContent>
                    <Box display="flex" alignItems="center" gap={1} mb={2}>
                        <Visibility color="primary" />
                        <Typography variant="h6">Key Insights</Typography>
                    </Box>

                    <Alert severity="info" sx={{ mb: 2 }}>
                        <Typography variant="body2" gutterBottom>
                            <strong>Top 3 Most Important Features:</strong>
                        </Typography>
                        <Box component="ol" sx={{ m: 0, pl: 2 }}>
                            {topFeatures.slice(0, 3).map(([name, value]) => (
                                <li key={name}>
                                    <Typography variant="body2">
                                        <strong>{name}</strong>: {(Math.abs(value) * 100).toFixed(2)}% importance
                                    </Typography>
                                </li>
                            ))}
                        </Box>
                    </Alert>

                    <Typography variant="body2" color="text.secondary">
                        💡 <strong>What this means:</strong> The model relies most heavily on{' '}
                        <strong>{topFeatures[0][0]}</strong> when making predictions. Features with higher
                        importance have a greater influence on the model's decisions. This transparency helps
                        ensure the model is making decisions based on appropriate factors.
                    </Typography>
                </CardContent>
            </Card>
            )}

            {/* Sample Predictions Card */}
            {transparencyData.sample_predictions && transparencyData.sample_predictions.length > 0 && (
                <Card sx={{ mt: 3 }}>
                    <CardContent>
                        <Box display="flex" alignItems="center" gap={1} mb={3}>
                            <Assessment color="primary" />
                            <Typography variant="h6">Sample Predictions with Explanations</Typography>
                        </Box>

                        <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 3 }}>
                            Below are {transparencyData.sample_predictions.length} example predictions showing how specific features 
                            contributed to each decision. Positive values push toward one class, negative toward the other.
                        </Typography>

                        <Box display="flex" flexDirection="column" gap={2}>
                            {transparencyData.sample_predictions.map((sample, idx) => {
                                const featureEntries = Object.entries(sample.top_features);
                                const maxAbsContribution = Math.max(
                                    ...featureEntries.map(([_, data]) => Math.abs(data.shap_contribution))
                                );

                                return (
                                    <Card key={idx} variant="outlined" sx={{ 
                                        bgcolor: sample.correct ? 'success.50' : 'error.50',
                                        borderColor: sample.correct ? 'success.main' : 'error.main',
                                        borderWidth: 2
                                    }}>
                                        <CardContent>
                                            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                                                <Box>
                                                    <Typography variant="subtitle1" fontWeight="bold">
                                                        Sample #{sample.sample_index}
                                                    </Typography>
                                                    <Box display="flex" gap={1} mt={1}>
                                                        <Chip 
                                                            label={`Predicted: ${sample.predicted_label}`}
                                                            color="primary"
                                                            size="small"
                                                        />
                                                        <Chip 
                                                            label={`Actual: ${sample.true_label}`}
                                                            color="default"
                                                            size="small"
                                                        />
                                                    </Box>
                                                </Box>
                                                <Chip 
                                                    label={sample.correct ? 'Correct' : 'Incorrect'}
                                                    color={sample.correct ? 'success' : 'error'}
                                                    sx={{ fontWeight: 'bold' }}
                                                />
                                            </Box>

                                            <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 2 }}>
                                                Base prediction value: {sample.base_value.toFixed(3)}
                                            </Typography>

                                            <Typography variant="subtitle2" gutterBottom>
                                                Top Contributing Features:
                                            </Typography>

                                            <Box display="flex" flexDirection="column" gap={1.5} mt={1}>
                                                {featureEntries.map(([featureName, data]) => {
                                                    const isPositive = data.shap_contribution > 0;
                                                    const barWidth = (Math.abs(data.shap_contribution) / maxAbsContribution) * 100;

                                                    return (
                                                        <Box key={featureName}>
                                                            <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
                                                                <Typography variant="body2" fontWeight="medium">
                                                                    {featureName}
                                                                </Typography>
                                                                <Typography variant="caption" color="text.secondary">
                                                                    Value: {typeof data.value === 'number' ? data.value.toFixed(2) : data.value}
                                                                </Typography>
                                                            </Box>
                                                            <Box display="flex" alignItems="center" gap={1}>
                                                                <Box flex={1} position="relative">
                                                                    <LinearProgress 
                                                                        variant="determinate" 
                                                                        value={barWidth}
                                                                        sx={{
                                                                            height: 8,
                                                                            borderRadius: 1,
                                                                            bgcolor: 'grey.200',
                                                                            '& .MuiLinearProgress-bar': {
                                                                                bgcolor: isPositive ? 'success.main' : 'error.main',
                                                                                borderRadius: 1
                                                                            }
                                                                        }}
                                                                    />
                                                                </Box>
                                                                <Typography 
                                                                    variant="body2" 
                                                                    fontWeight="bold"
                                                                    color={isPositive ? 'success.main' : 'error.main'}
                                                                    sx={{ minWidth: 60, textAlign: 'right' }}
                                                                >
                                                                    {isPositive ? '+' : ''}{data.shap_contribution.toFixed(3)}
                                                                </Typography>
                                                            </Box>
                                                        </Box>
                                                    );
                                                })}
                                            </Box>
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </Box>
                    </CardContent>
                </Card>
            )}

                        {/* Debug Section - Remove after testing */}
                        <Card sx={{ mt: 3, bgcolor: 'grey.100' }}>
                            <CardContent>
                                <Typography variant="h6" gutterBottom>Debug Info</Typography>
                                <Typography variant="caption" component="pre" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                                    {JSON.stringify({
                                        hasSamplePredictions: !!transparencyData.sample_predictions,
                                        samplePredictionsLength: transparencyData.sample_predictions?.length || 0,
                                        samplePredictionsData: transparencyData.sample_predictions
                                    }, null, 2)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Box>
                );
            }
