import { Box, Card, CardContent, Typography, Chip } from '@mui/material';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

interface ContributionItem {
    feature: string;
    weight: number;
}

interface LIMEVisualizationProps {
    prediction: number;
    contributions: ContributionItem[];
}

export default function LIMEVisualization({ prediction, contributions }: LIMEVisualizationProps) {
    const top = contributions.slice(0, 10);
    const predictionLabel = prediction >= 0.5 ? 'Positive' : 'Negative';

    return (
        <Card>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6">LIME Explanation</Typography>
                    <Chip label={`Prediction: ${prediction.toFixed(3)} (${predictionLabel})`} color="primary" />
                </Box>

                <Box sx={{ height: 340 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={top} layout="vertical" margin={{ left: 60, right: 10, top: 10, bottom: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis type="number" />
                            <YAxis dataKey="feature" type="category" width={170} />
                            <Tooltip />
                            <Bar dataKey="weight" fill="#22c55e" />
                        </BarChart>
                    </ResponsiveContainer>
                </Box>

                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                    Positive bars increase probability for the predicted class; smaller/negative contributions indicate opposite influence.
                </Typography>
            </CardContent>
        </Card>
    );
}
