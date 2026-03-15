import { Box, Card, CardContent, Typography, Table, TableBody, TableCell, TableHead, TableRow, Paper } from '@mui/material';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts';

interface FairnessMetric {
    name: string;
    value: number;
    threshold: number;
    by_group?: Record<string, number>;
}

interface ConfusionMatrix {
    group: string;
    tp: number;
    fp: number;
    tn: number;
    fn: number;
}

interface FairnessVisualizationProps {
    metrics: FairnessMetric[];
    confusion_matrices: ConfusionMatrix[];
}

export default function FairnessVisualization({ metrics, confusion_matrices }: FairnessVisualizationProps) {
    const barData = metrics.map((m) => ({ metric: m.name, value: m.value, threshold: m.threshold }));
    
    // Normalize metrics to [0, 1] range for radar chart
    // Ratio metrics are already 0-1, but clamp just in case
    // Difference metrics should also be 0-1
    const radarData = metrics.map((m) => ({ 
        metric: m.name, 
        actual: Math.min(Math.max(m.value, 0), 1),  // Clamp to [0, 1]
        threshold: Math.min(Math.max(m.threshold, 0), 1),  // Clamp threshold too
        reference: 0.8,
    }));

    const groupData = metrics[0]?.by_group
        ? Object.entries(metrics[0].by_group).map(([group, rate]) => ({ group, rate }))
        : [];

    return (
        <Box sx={{ display: 'grid', gap: 2 }}>
            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>Fairness Metrics vs Thresholds</Typography>
                    <Box sx={{ height: 320 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={barData} margin={{ top: 10, left: 10, right: 10, bottom: 40 }}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="metric" angle={-20} textAnchor="end" height={70} />
                                <YAxis />
                                <Tooltip />
                                <Bar dataKey="value" fill="#3b82f6" />
                                <Bar dataKey="threshold" fill="#f59e0b" />
                            </BarChart>
                        </ResponsiveContainer>
                    </Box>
                </CardContent>
            </Card>

            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>Demographic Parity by Group</Typography>
                    <Box sx={{ height: 300 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={groupData}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="group" />
                                <YAxis />
                                <Tooltip />
                                <Bar dataKey="rate" fill="#14b8a6" />
                            </BarChart>
                        </ResponsiveContainer>
                    </Box>
                </CardContent>
            </Card>

            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>Fairness Radar</Typography>
                    <Box sx={{ height: 340 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <RadarChart data={radarData}>
                                <PolarGrid gridType="polygon" />
                                <PolarAngleAxis dataKey="metric" />
                                <PolarRadiusAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
                                <Radar name="Actual" dataKey="actual" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.35} />
                                <Radar name="Threshold" dataKey="threshold" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.2} />
                                    {/* Threshold reference ring at 0.8 (common fairness threshold) */}
                                    <Radar name="0.8 Rule" dataKey="reference" stroke="#ef4444" strokeDasharray="5 5" fill="transparent" />
                                <Tooltip />
                            </RadarChart>
                        </ResponsiveContainer>
                    </Box>
                </CardContent>
            </Card>

            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>Confusion Matrix by Group</Typography>
                    <Paper variant="outlined">
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Group</TableCell>
                                    <TableCell align="right">TP</TableCell>
                                    <TableCell align="right">FP</TableCell>
                                    <TableCell align="right">TN</TableCell>
                                    <TableCell align="right">FN</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {confusion_matrices.map((row) => (
                                    <TableRow key={row.group}>
                                        <TableCell>{row.group}</TableCell>
                                        <TableCell align="right">{row.tp}</TableCell>
                                        <TableCell align="right">{row.fp}</TableCell>
                                        <TableCell align="right">{row.tn}</TableCell>
                                        <TableCell align="right">{row.fn}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </Paper>
                </CardContent>
            </Card>
        </Box>
    );
}
