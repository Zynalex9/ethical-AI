import { Box, Card, CardContent, Typography, Chip, Table, TableHead, TableRow, TableCell, TableBody, Paper } from '@mui/material';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, RadialBarChart, RadialBar } from 'recharts';

interface PrivacyVisualizationProps {
    piiDetected: string[];
    kAnonymityGroups?: Array<{ size: number; count: number }>;
    riskScore: number;
}

export default function PrivacyVisualization({ piiDetected, kAnonymityGroups = [], riskScore }: PrivacyVisualizationProps) {
    const gaugeData = [{ name: 'Risk', value: Math.max(0, Math.min(100, riskScore)) }];
    const riskLevel = riskScore >= 70 ? 'High' : riskScore >= 30 ? 'Medium' : 'Low';
    const riskColor = riskScore >= 70 ? 'error' : riskScore >= 30 ? 'warning' : 'success';

    return (
        <Box sx={{ display: 'grid', gap: 2 }}>
            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>PII Detection</Typography>
                    {piiDetected.length === 0 ? (
                        <Chip label="No PII columns detected" color="success" />
                    ) : (
                        <Paper variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Column Name</TableCell>
                                        <TableCell>PII Type</TableCell>
                                        <TableCell>Risk</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {piiDetected.map((col) => (
                                        <TableRow key={col}>
                                            <TableCell>{col}</TableCell>
                                            <TableCell>Sensitive Identifier</TableCell>
                                            <TableCell><Chip size="small" color="error" label="High" /></TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </Paper>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>k-Anonymity Group Distribution</Typography>
                    {kAnonymityGroups.length === 0 ? (
                        <Box sx={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Typography variant="body2" color="text.secondary">
                                No k-anonymity data available. Run a privacy validation with k-anonymity enabled.
                            </Typography>
                        </Box>
                    ) : (
                        <Box sx={{ height: 280 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={kAnonymityGroups}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="size" label={{ value: 'Group Size', position: 'insideBottom', offset: -5 }} />
                                    <YAxis label={{ value: 'Number of Groups', angle: -90, position: 'insideLeft' }} />
                                    <Tooltip />
                                    <Bar dataKey="count" fill="#3b82f6" />
                                </BarChart>
                            </ResponsiveContainer>
                        </Box>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>Privacy Risk Score</Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                        <Box sx={{ width: 220, height: 220 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <RadialBarChart innerRadius="70%" outerRadius="100%" data={gaugeData} startAngle={180} endAngle={0}>
                                    <RadialBar background dataKey="value" fill="#f59e0b" />
                                </RadialBarChart>
                            </ResponsiveContainer>
                        </Box>
                        <Box>
                            <Typography variant="h3" sx={{ fontWeight: 700 }}>{riskScore.toFixed(0)}%</Typography>
                            <Chip color={riskColor as any} label={`${riskLevel} Risk`} />
                        </Box>
                    </Box>
                </CardContent>
            </Card>
        </Box>
    );
}
