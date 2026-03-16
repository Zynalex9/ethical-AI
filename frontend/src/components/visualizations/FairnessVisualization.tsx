import { Box, Card, CardContent, Typography, Table, TableBody, TableCell, TableHead, TableRow, Paper } from '@mui/material';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend, Cell } from 'recharts';

interface FairnessMetric {
    name: string;
    value: number;
    threshold: number;
    by_group?: Record<string, number | Record<string, number>>;
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

// Safely extract a single numeric rate from a by_group entry value.
// The backend may send:
//   { "Male": 0.72 }                        → plain number   ✓
//   { "Male": { "0": 0.28, "1": 0.72 } }   → nested object  → take "1" key (positive class) or average
//   { "Male": { "rate": 0.72 } }            → keyed object   → first numeric value
function extractRate(v: number | Record<string, number>): number {
    if (typeof v === 'number') return v;
    if (typeof v === 'object' && v !== null) {
        const vals = Object.values(v).filter((x) => typeof x === 'number') as number[];
        if (vals.length === 0) return 0;
        if (typeof (v as any)['1'] === 'number') return (v as any)['1'];
        return vals.reduce((a, b) => a + b, 0) / vals.length;
    }
    return 0;
}

// Find the first metric that has meaningful by_group data.
function buildGroupData(metrics: FairnessMetric[]): { group: string; rate: number; metricName: string }[] {
    for (const m of metrics) {
        if (!m.by_group || typeof m.by_group !== 'object') continue;
        const entries = Object.entries(m.by_group);
        if (entries.length === 0) continue;
        const rows = entries.map(([group, v]) => ({
            group: String(group),
            rate: Number(extractRate(v as any).toFixed(4)),
            metricName: m.name,
        }));
        if (rows.some((r) => r.rate !== 0)) return rows;
    }
    return [];
}

const GROUP_COLORS = ['#3b82f6', '#14b8a6', '#f59e0b', '#a855f7', '#ef4444', '#22c55e'];

/** Round to 2 decimal places for tooltip display */
const fmt2dp = (v: number | undefined) => (v == null ? '' : Number(v).toFixed(2));

export default function FairnessVisualization({ metrics, confusion_matrices }: FairnessVisualizationProps) {
    const barData = metrics.map((m) => ({ metric: m.name, value: m.value, threshold: m.threshold }));

    // Normalize metrics to [0, 1] range for radar chart
    // Ratio metrics are already 0-1, but clamp just in case
    // Difference metrics should also be 0-1
    const radarData = metrics.map((m) => ({
        metric: m.name,
        actual: Math.min(Math.max(m.value, 0), 1),
        threshold: Math.min(Math.max(m.threshold, 0), 1),
    }));

    const groupData = buildGroupData(metrics);
    const groupMetricLabel = groupData[0]?.metricName
        ? groupData[0].metricName.replace(/_/g, ' ')
        : '';

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
                                <Tooltip formatter={(v: number | undefined) => fmt2dp(v)} />
                                <Legend verticalAlign="top" />
                                <Bar dataKey="value" name="Actual Value" fill="#3b82f6" />
                                <Bar dataKey="threshold" name="Threshold" fill="#f59e0b" />
                            </BarChart>
                        </ResponsiveContainer>
                    </Box>
                </CardContent>
            </Card>

            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 0.5 }}>
                        Demographic Parity by Group
                    </Typography>
                    {groupMetricLabel && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
                            Showing selection rates from: <strong>{groupMetricLabel}</strong>
                        </Typography>
                    )}

                    {groupData.length > 0 ? (
                        <Box sx={{ height: 300 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart
                                    data={groupData}
                                    margin={{ top: 10, left: 10, right: 10, bottom: 10 }}
                                >
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="group" />
                                    <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                                    <Tooltip
                                        formatter={(value: number | undefined) => [value == null ? 'N/A' : `${(value * 100).toFixed(2)}%`, 'Selection Rate']}
                                    />
                                    <Bar dataKey="rate" name="Selection Rate" radius={[4, 4, 0, 0]}>
                                        {groupData.map((_, idx) => (
                                            <Cell key={idx} fill={GROUP_COLORS[idx % GROUP_COLORS.length]} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </Box>
                    ) : (
                        <Box
                            sx={{
                                height: 200,
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                justifyContent: 'center',
                                border: '1px dashed',
                                borderColor: 'divider',
                                borderRadius: 2,
                                color: 'text.secondary',
                                gap: 1,
                            }}
                        >
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                No per-group data available
                            </Typography>
                            <Typography variant="caption" sx={{ maxWidth: 360, textAlign: 'center' }}>
                                Per-group selection rates are included when fairness validation runs with a
                                sensitive feature column. Ensure the validation included a target column
                                and that the backend returned <code>selection_rates</code> in metric details.
                            </Typography>
                        </Box>
                    )}
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
                                <Legend />
                                <Tooltip formatter={(v: number | undefined) => fmt2dp(v)} />
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
                                {confusion_matrices.length > 0 ? (
                                    confusion_matrices.map((row) => (
                                        <TableRow key={row.group}>
                                            <TableCell>{row.group}</TableCell>
                                            <TableCell align="right">{row.tp}</TableCell>
                                            <TableCell align="right">{row.fp}</TableCell>
                                            <TableCell align="right">{row.tn}</TableCell>
                                            <TableCell align="right">{row.fn}</TableCell>
                                        </TableRow>
                                    ))
                                ) : (
                                    <TableRow>
                                        <TableCell colSpan={5} align="center" sx={{ color: 'text.secondary', py: 3 }}>
                                            No confusion matrix data available
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </Paper>
                </CardContent>
            </Card>
        </Box>
    );
}
