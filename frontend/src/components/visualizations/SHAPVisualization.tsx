import { Box, Card, CardContent, Typography } from '@mui/material';
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ScatterChart,
    Scatter,
    ZAxis,
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

    const summaryPoints = localExplanations.flatMap((row) =>
        row.contributions.map((c) => ({
            feature: c.feature,
            shap: c.shap,
            value: c.value,
            sample: row.sample_index,
        }))
    );

    const firstLocal = localExplanations[0]?.contributions ?? [];

    return (
        <Box sx={{ display: 'grid', gap: 2 }}>
            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>Global Feature Importance (Top 10)</Typography>
                    <Box sx={{ height: 320 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={topGlobal} margin={{ left: 10, right: 10, top: 10, bottom: 30 }}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="feature" angle={-25} textAnchor="end" height={60} />
                                <YAxis />
                                <Tooltip />
                                <Bar dataKey="importance" fill="#3b82f6" />
                            </BarChart>
                        </ResponsiveContainer>
                    </Box>
                </CardContent>
            </Card>

            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>Local Explanation (Sample {localExplanations[0]?.sample_index ?? '-'})</Typography>
                    <Box sx={{ height: 320 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={firstLocal} layout="vertical" margin={{ left: 60, right: 10, top: 10, bottom: 10 }}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis type="number" />
                                <YAxis dataKey="feature" type="category" width={160} />
                                <Tooltip />
                                <Bar dataKey="shap" fill="#14b8a6" />
                            </BarChart>
                        </ResponsiveContainer>
                    </Box>
                </CardContent>
            </Card>

            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>SHAP Summary (scatter)</Typography>
                    <Box sx={{ height: 360 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <ScatterChart margin={{ left: 20, right: 20, top: 20, bottom: 20 }}>
                                <CartesianGrid />
                                <XAxis type="number" dataKey="shap" name="SHAP" />
                                <YAxis type="number" dataKey="sample" name="Sample" />
                                <ZAxis type="number" dataKey="value" range={[20, 120]} name="Feature value" />
                                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                                <Scatter data={summaryPoints} fill="#3b82f6" />
                            </ScatterChart>
                        </ResponsiveContainer>
                    </Box>
                </CardContent>
            </Card>
        </Box>
    );
}
