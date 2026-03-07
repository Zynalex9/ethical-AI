import React, { useState } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Card,
    CardContent,
    CardActions,
    Typography,
    Chip,
    Alert,
    CircularProgress,
    Box,
    Stack
} from '@mui/material';
import {
    Gavel as GavelIcon,
    Work as WorkIcon,
    AccountBalance as BankIcon,
    Download as DownloadIcon
} from '@mui/icons-material';

interface BenchmarkDataset {
    name: string;
    description: string;
    filename: string;
    target_column: string;
    sensitive_attributes: string[];
    key_features: string[];
    domain: string;
    reference: string;
}

interface BenchmarkDatasetLoaderProps {
    open: boolean;
    onClose: () => void;
    projectId: string;
    onSuccess: (datasetName: string) => void;
}

const DATASET_ICONS: Record<string, React.ReactElement> = {
    criminal_justice: <GavelIcon sx={{ fontSize: 40 }} />,
    employment: <WorkIcon sx={{ fontSize: 40 }} />,
    finance: <BankIcon sx={{ fontSize: 40 }} />
};

const DATASET_COLORS: Record<string, 'primary' | 'secondary' | 'success'> = {
    criminal_justice: 'primary',
    employment: 'secondary',
    finance: 'success'
};

export default function BenchmarkDatasetLoader({
    open,
    onClose,
    projectId,
    onSuccess
}: BenchmarkDatasetLoaderProps) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loadingDataset, setLoadingDataset] = useState<string | null>(null);

    const benchmarkDatasets: Record<string, BenchmarkDataset> = {
        compas: {
            name: 'COMPAS Recidivism',
            description: 'Criminal recidivism risk assessment dataset from Broward County, Florida. Used to study racial bias in algorithmic risk assessment tools.',
            filename: 'compas-scores-raw.csv',
            target_column: 'two_year_recid',
            sensitive_attributes: ['race', 'sex', 'age_cat'],
            key_features: ['age', 'priors_count', 'c_charge_degree', 'decile_score'],
            domain: 'criminal_justice',
            reference: 'ProPublica COMPAS Analysis (2016)'
        },
        adult_income: {
            name: 'Adult Income (Census)',
            description: 'Census data from 1994 used to predict whether income exceeds $50K/year. Widely used for fairness research.',
            filename: 'adult.csv',
            target_column: 'income',
            sensitive_attributes: ['sex', 'race', 'native-country'],
            key_features: ['age', 'education', 'occupation', 'hours-per-week', 'marital-status'],
            domain: 'employment',
            reference: 'UCI Machine Learning Repository'
        },
        german_credit: {
            name: 'German Credit',
            description: 'Credit risk assessment dataset from a German bank. Used for fairness in lending and ECOA compliance studies.',
            filename: 'german_credit_data.csv',
            target_column: 'credit_risk',
            sensitive_attributes: ['sex', 'age', 'foreign_worker'],
            key_features: ['duration', 'credit_amount', 'installment_rate', 'property', 'existing_credits'],
            domain: 'finance',
            reference: 'UCI Machine Learning Repository - Statlog German Credit'
        }
    };

    const handleLoadDataset = async (datasetKey: string) => {
        setLoading(true);
        setError(null);
        setLoadingDataset(datasetKey);

        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(
                `${import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'}/datasets/project/${projectId}/load-benchmark?dataset_key=${datasetKey}`,
                {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to load dataset');
            }

            await response.json();
            onSuccess(benchmarkDatasets[datasetKey].name);
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
        } finally {
            setLoading(false);
            setLoadingDataset(null);
        }
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="md"
            fullWidth
        >
            <DialogTitle>
                Load Benchmark Dataset
            </DialogTitle>
            <DialogContent>
                {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                        {error}
                    </Alert>
                )}

                <Typography variant="body2" color="text.secondary" paragraph>
                    Select a pre-configured benchmark dataset to quickly test fairness validation.
                    These datasets are widely used in AI ethics research.
                </Typography>

                <Stack spacing={2}>
                    {Object.entries(benchmarkDatasets).map(([key, dataset]) => (
                        <Card variant="outlined" key={key}>
                            <CardContent>
                                <Box display="flex" alignItems="flex-start" gap={2}>
                                        <Box
                                            sx={{
                                                color: `${DATASET_COLORS[dataset.domain]}.main`,
                                                display: 'flex',
                                                alignItems: 'center'
                                            }}
                                        >
                                            {DATASET_ICONS[dataset.domain]}
                                        </Box>
                                        <Box flex={1}>
                                            <Typography variant="h6" gutterBottom>
                                                {dataset.name}
                                            </Typography>
                                            <Typography variant="body2" color="text.secondary" paragraph>
                                                {dataset.description}
                                            </Typography>

                                            <Box mb={1}>
                                                <Typography variant="caption" color="text.secondary">
                                                    Sensitive Attributes:
                                                </Typography>
                                                <Box mt={0.5}>
                                                    {dataset.sensitive_attributes.map((attr) => (
                                                        <Chip
                                                            key={attr}
                                                            label={attr}
                                                            size="small"
                                                            sx={{ mr: 0.5, mb: 0.5 }}
                                                        />
                                                    ))}
                                                </Box>
                                            </Box>

                                            <Typography variant="caption" color="text.secondary" display="block">
                                                Target: <strong>{dataset.target_column}</strong>
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" display="block">
                                                Reference: {dataset.reference}
                                            </Typography>
                                        </Box>
                                    </Box>
                                </CardContent>
                                <CardActions>
                                    <Button
                                        onClick={() => handleLoadDataset(key)}
                                        variant="contained"
                                        color={DATASET_COLORS[dataset.domain]}
                                        startIcon={
                                            loadingDataset === key ? (
                                                <CircularProgress size={20} color="inherit" />
                                            ) : (
                                                <DownloadIcon />
                                            )
                                        }
                                        disabled={loading}
                                    >
                                        {loadingDataset === key ? 'Loading...' : 'Load Dataset'}
                                    </Button>
                                </CardActions>
                            </Card>
                    ))}
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} disabled={loading}>
                    Cancel
                </Button>
            </DialogActions>
        </Dialog>
    );
}
