import { Box, Card, CardContent, Typography, Chip, Alert } from '@mui/material';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from 'recharts';

interface ContributionItem {
    feature: string;
    weight: number;
}

interface LIMEVisualizationProps {
    prediction: number;
    contributions: ContributionItem[];
}

export default function LIMEVisualization({ prediction, contributions }: LIMEVisualizationProps) {
    const top = contributions.slice(0, 8);
    const predictionLabel = prediction >= 0.5 ? 'Positive' : 'Negative';
    const hasContributions = top.some(c => Math.abs(c.weight) > 1e-6);

    return (
        <Card variant="outlined">
            <CardContent sx={{ pb: '12px !important' }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="subtitle1" fontWeight={700}>LIME Explanation</Typography>
                    <Chip label={`Pred: ${prediction.toFixed(3)} (${predictionLabel})`} color="primary" size="small" />
                </Box>

                {hasContributions ? (
                    <Box sx={{ height: 220 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={top} layout="vertical" margin={{ left: 50, right: 8, top: 4, bottom: 4 }}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis type="number" tick={{ fontSize: 11 }} />
                                <YAxis dataKey="feature" type="category" width={120} tick={{ fontSize: 11 }} />
                                <Tooltip />
                                <Bar dataKey="weight" radius={[0, 3, 3, 0]}>
                                    {top.map((entry, idx) => (
                                        <Cell key={idx} fill={entry.weight >= 0 ? '#22c55e' : '#ef4444'} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </Box>
                ) : (
                    <Alert severity="info" variant="outlined" sx={{ mt: 1 }}>
                        All LIME feature contributions are near zero — the model prediction is roughly uniform across feature perturbations.
                    </Alert>
                )}

                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    Green bars increase predicted-class probability; red bars decrease it.
                </Typography>
            </CardContent>
        </Card>
    );
}
