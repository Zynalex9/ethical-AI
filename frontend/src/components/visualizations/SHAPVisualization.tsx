import { Box, Card, CardContent, Typography, Alert } from '@mui/material';
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
} from 'recharts';

interface GlobalImportanceItem {
    feature: string;
    importance: number;
}

interface LocalContributionItem {
    feature: string;
    value: number;
    shap: number;
}

interface LocalExplanation {
    sample_index: number;
    prediction: number;
    contributions: LocalContributionItem[];
}

interface SHAPVisualizationProps {
    globalImportance: GlobalImportanceItem[];
    localExplanations: LocalExplanation[];
}

export default function SHAPVisualization({ globalImportance, localExplanations }: SHAPVisualizationProps) {
    const topGlobal = globalImportance.slice(0, 10);
    const firstLocal = localExplanations[0]?.contributions ?? [];
    const hasGlobal = topGlobal.length > 0 && topGlobal.some(g => g.importance > 0);
    const hasLocal = firstLocal.length > 0 && firstLocal.some(c => Math.abs(c.shap) > 1e-6);

    return (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
            {/* Global Feature Importance */}
            <Card variant="outlined">
                <CardContent sx={{ pb: '12px !important' }}>
                    <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>Global Feature Importance</Typography>
                    {hasGlobal ? (
                        <Box sx={{ height: 220 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={topGlobal} margin={{ left: 0, right: 8, top: 4, bottom: 24 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="feature" angle={-20} textAnchor="end" height={50} tick={{ fontSize: 11 }} />
                                    <YAxis tick={{ fontSize: 11 }} />
                                    <Tooltip />
                                    <Bar dataKey="importance" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </Box>
                    ) : (
                        <Alert severity="info" variant="outlined" sx={{ mt: 1 }}>No significant feature importance data available.</Alert>
                    )}
                </CardContent>
            </Card>

            {/* Local Explanation */}
            <Card variant="outlined">
                <CardContent sx={{ pb: '12px !important' }}>
                    <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>
                        Local SHAP (Sample {localExplanations[0]?.sample_index ?? '-'})
                    </Typography>
                    {hasLocal ? (
                        <Box sx={{ height: 220 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={firstLocal.slice(0, 8)} layout="vertical" margin={{ left: 50, right: 8, top: 4, bottom: 4 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis type="number" tick={{ fontSize: 11 }} />
                                    <YAxis dataKey="feature" type="category" width={120} tick={{ fontSize: 11 }} />
                                    <Tooltip />
                                    <Bar dataKey="shap" fill="#14b8a6" radius={[0, 3, 3, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </Box>
                    ) : (
                        <Alert severity="info" variant="outlined" sx={{ mt: 1 }}>No significant SHAP contributions for local samples.</Alert>
                    )}
                </CardContent>
            </Card>
        </Box>
    );
}
