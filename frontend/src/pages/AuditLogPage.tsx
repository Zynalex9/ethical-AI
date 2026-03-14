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

    const logRows = Array.isArray(logs)
        ? logs
        : Array.isArray(logs?.items)
            ? logs.items
            : Array.isArray(logs?.data)
                ? logs.data
                : [];

    const totalRows = typeof logs?.total === 'number'
        ? logs.total
        : typeof logs?.count === 'number'
            ? logs.count
            : -1;

    const truncateUuid = (value?: string | null) => {
        if (!value) return 'System';
        return value.length > 12 ? `${value.slice(0, 8)}...` : value;
    };

    const summarizeDetails = (details: any) => {
        if (!details || typeof details !== 'object') return 'No details';
        const entries = Object.entries(details).slice(0, 2);
        if (entries.length === 0) return 'No details';
        return entries
            .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
            .join(' | ');
    };

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
                                        <TableCell>User</TableCell>
                                        <TableCell>Details</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {logRows.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={5} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                                                No audit records found.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                    {logRows.map((log: any) => (
                                        <TableRow key={log.id}>
                                            <TableCell>{new Date(log.created_at || log.timestamp).toLocaleString()}</TableCell>
                                            <TableCell>
                                                <Chip label={log.action} size="small" variant="outlined" />
                                            </TableCell>
                                            <TableCell>
                                                {log.resource_type}
                                                {log.resource_id ? ` • ${truncateUuid(String(log.resource_id))}` : ''}
                                            </TableCell>
                                            <TableCell>{log.user_email || truncateUuid(String(log.user_id || ''))}</TableCell>
                                            <TableCell>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                    <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 320 }} noWrap>
                                                        {summarizeDetails(log.details)}
                                                    </Typography>
                                                    <IconButton size="small" onClick={() => setSelectedLog(log)}>
                                                        <ViewIcon />
                                                    </IconButton>
                                                </Box>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                        <TablePagination
                            component="div"
                            count={totalRows}
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
                    <Box
                        component="pre"
                        sx={{
                            p: 2,
                            bgcolor: (theme) =>
                                theme.palette.mode === 'dark'
                                    ? 'rgba(255,255,255,0.06)'
                                    : 'grey.100',
                            color: 'text.primary',
                            border: '1px solid',
                            borderColor: 'divider',
                            borderRadius: 1,
                            overflow: 'auto',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            fontFamily: 'monospace',
                            fontSize: '0.85rem',
                        }}
                    >
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
