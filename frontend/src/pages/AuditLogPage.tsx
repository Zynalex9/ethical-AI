// Audit Log Page

import { useState } from 'react';
import {
    Box,
    Container,
    Typography,
    Card,
    CardContent,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TablePagination,
    Grid,
    Chip,
    CircularProgress,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button
} from '@mui/material';
import { Refresh as RefreshIcon, Visibility as ViewIcon } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { auditApi } from '../services/api';

export default function AuditLogPage() {
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(25);
    const [selectedLog, setSelectedLog] = useState<any>(null);

    const { data: logs, isLoading, refetch } = useQuery({
        queryKey: ['audit', page, rowsPerPage],
        queryFn: () => auditApi.list({ skip: page * rowsPerPage, limit: rowsPerPage }),
    });

    const { data: summary } = useQuery({
        queryKey: ['audit-summary'],
        queryFn: auditApi.getSummary,
        retry: false, // Don't retry on 403 (non-admin users)
        meta: { ignoreError: true } // Suppress error notifications
    });

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 4 }}>
                <Typography variant="h4">Audit Log</Typography>
                <IconButton onClick={() => refetch()}>
                    <RefreshIcon />
                </IconButton>
            </Box>

            {summary && (
                <Grid container spacing={3} sx={{ mb: 4 }}>
                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <Card>
                            <CardContent>
                                <Typography variant="body2" color="text.secondary">Total Events</Typography>
                                <Typography variant="h4">{summary.total_events?.toLocaleString()}</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <Card>
                            <CardContent>
                                <Typography variant="body2" color="text.secondary">Today</Typography>
                                <Typography variant="h4">{summary.events_today?.toLocaleString()}</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <Card>
                            <CardContent>
                                <Typography variant="body2" color="text.secondary">This Week</Typography>
                                <Typography variant="h4">{summary.events_this_week?.toLocaleString()}</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <Card>
                            <CardContent>
                                <Typography variant="body2" color="text.secondary">Action Types</Typography>
                                <Typography variant="h4">{Object.keys(summary.by_action || {}).length}</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            )}

            <Card>
                {isLoading ? <CircularProgress sx={{ m: 4 }} /> : (
                    <>
                        <TableContainer>
                            <Table>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Date</TableCell>
                                        <TableCell>Action</TableCell>
                                        <TableCell>Resource</TableCell>
                                        <TableCell>User ID</TableCell>
                                        <TableCell>Details</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {logs?.map((log: any) => (
                                        <TableRow key={log.id}>
                                            <TableCell>{new Date(log.created_at).toLocaleString()}</TableCell>
                                            <TableCell>
                                                <Chip label={log.action} size="small" variant="outlined" />
                                            </TableCell>
                                            <TableCell>{log.resource_type}</TableCell>
                                            <TableCell>{log.user_id}</TableCell>
                                            <TableCell>
                                                <IconButton size="small" onClick={() => setSelectedLog(log)}>
                                                    <ViewIcon />
                                                </IconButton>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                        <TablePagination
                            component="div"
                            count={-1}
                            rowsPerPage={rowsPerPage}
                            page={page}
                            onPageChange={(_, p) => setPage(p)}
                            onRowsPerPageChange={(e) => {
                                setRowsPerPage(parseInt(e.target.value, 10));
                                setPage(0);
                            }}
                        />
                    </>
                )}
            </Card>

            <Dialog open={!!selectedLog} onClose={() => setSelectedLog(null)}>
                <DialogTitle>Audit Details</DialogTitle>
                <DialogContent>
                    <Box component="pre" sx={{ p: 2, bgcolor: 'grey.100', borderRadius: 1, overflow: 'auto' }}>
                        {JSON.stringify(selectedLog?.details, null, 2)}
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSelectedLog(null)}>Close</Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
}
