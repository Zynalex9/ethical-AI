/**
 * TraceabilityMatrix – Phase 3.3
 *
 * Displays the Requirement Traceability Matrix with:
 *  - Table view: Requirement → Dataset → Model → Validation Result → Status
 *  - Color-coded rows (green=pass, red=fail, grey=not validated)
 *  - Filtering by principle and status
 *  - Expandable rows with detailed results
 *  - CSV export
 */

import { useState, useMemo } from 'react';
import {
    Box,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Chip,
    IconButton,
    Collapse,
    Typography,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    TextField,
    Button,
    Tooltip,
    Stack,
    Alert,
    LinearProgress,
} from '@mui/material';
import {
    KeyboardArrowDown as ExpandIcon,
    KeyboardArrowUp as CollapseIcon,
    Download as DownloadIcon,
    FilterList as FilterIcon,
} from '@mui/icons-material';

/* ---------- types ---------- */
export interface TraceEntry {
    requirement: {
        id: string;
        name: string;
        principle: string;
        description?: string;
        status: string;
        specification?: Record<string, any>;
        elicited_automatically?: boolean;
        confidence_score?: number | null;
        created_at?: string;
    } | null;
    dataset: {
        id: string;
        name: string;
        row_count: number;
        column_count: number;
        sensitive_attributes: string[];
        target_column: string | null;
    } | null;
    model: {
        id: string;
        name: string;
        model_type: string;
        version: string;
    } | null;
    validation: {
        id: string;
        status: string;
        behavior_pattern: string | null;
        affected_groups: string[] | null;
        started_at: string | null;
        completed_at: string | null;
        mlflow_run_id: string | null;
        results: {
            metric_name: string;
            metric_value: number | null;
            threshold: number | null;
            passed: boolean;
            principle: string;
            details?: Record<string, any>;
        }[];
    } | null;
    status: 'pass' | 'fail' | 'not_validated' | 'unknown';
    suite_id?: string | null;
    unlinked_principle?: string | null;
}

export interface TraceSummary {
    total_requirements: number;
    total_validations: number;
    pass_count: number;
    fail_count: number;
    not_validated_count: number;
    pass_rate: number;
}

interface Props {
    traces: TraceEntry[];
    summary?: TraceSummary;
    loading?: boolean;
    onViewRootCause?: (validationId: string) => void;
}

/* ---------- helpers ---------- */
const statusColor = (status: string) => {
    switch (status) {
        case 'pass':
            return 'success';
        case 'fail':
            return 'error';
        case 'not_validated':
            return 'default';
        default:
            return 'warning';
    }
};

const statusLabel = (status: string) => {
    switch (status) {
        case 'pass':
            return 'Pass';
        case 'fail':
            return 'Fail';
        case 'not_validated':
            return 'Not Validated';
        default:
            return 'Unknown';
    }
};

const principleChipColor = (p: string): 'primary' | 'secondary' | 'success' | 'warning' | 'info' => {
    switch (p) {
        case 'fairness': return 'primary';
        case 'privacy': return 'secondary';
        case 'transparency': return 'info';
        case 'accountability': return 'warning';
        default: return 'primary';
    }
};

/* ---------- Expandable Row ---------- */
function TraceRow({
    trace,
    onViewRootCause,
}: {
    trace: TraceEntry;
    onViewRootCause?: (id: string) => void;
}) {
    const [open, setOpen] = useState(false);
    const results = trace.validation?.results ?? [];

    const rowBg =
        trace.status === 'pass'
            ? 'rgba(46,125,50,0.04)'
            : trace.status === 'fail'
                ? 'rgba(211,47,47,0.04)'
                : 'transparent';

    return (
        <>
            <TableRow sx={{ backgroundColor: rowBg, '& > *': { borderBottom: 'unset' } }}>
                <TableCell padding="checkbox">
                    {results.length > 0 && (
                        <IconButton size="small" onClick={() => setOpen(!open)}>
                            {open ? <CollapseIcon /> : <ExpandIcon />}
                        </IconButton>
                    )}
                </TableCell>
                <TableCell>
                    {trace.requirement ? (
                        <Box>
                            <Typography variant="body2" fontWeight={600}>
                                {trace.requirement.name}
                            </Typography>
                            <Chip
                                size="small"
                                label={trace.requirement.principle}
                                color={principleChipColor(trace.requirement.principle)}
                                sx={{ mt: 0.5 }}
                            />
                        </Box>
                    ) : (
                        <Typography variant="body2" color="text.secondary">
                            —
                        </Typography>
                    )}
                </TableCell>
                <TableCell>
                    {trace.dataset ? trace.dataset.name : '—'}
                </TableCell>
                <TableCell>
                    {trace.model ? (
                        <Tooltip title={`Type: ${trace.model.model_type} | v${trace.model.version}`}>
                            <span>{trace.model.name}</span>
                        </Tooltip>
                    ) : (
                        '—'
                    )}
                </TableCell>
                <TableCell>
                    {trace.validation ? (
                        <Box>
                            <Typography variant="body2">
                                {results.filter((r) => r.passed).length}/{results.length} metrics passed
                            </Typography>
                            {trace.validation.behavior_pattern && (
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                                    {trace.validation.behavior_pattern.slice(0, 100)}
                                    {trace.validation.behavior_pattern.length > 100 ? '…' : ''}
                                </Typography>
                            )}
                        </Box>
                    ) : (
                        <Typography variant="body2" color="text.secondary">
                            Not validated
                        </Typography>
                    )}
                </TableCell>
                <TableCell>
                    <Chip
                        label={statusLabel(trace.status)}
                        color={statusColor(trace.status) as any}
                        size="small"
                    />
                </TableCell>
            </TableRow>

            {/* Expanded detail row */}
            <TableRow>
                <TableCell colSpan={6} sx={{ py: 0 }}>
                    <Collapse in={open} timeout="auto" unmountOnExit>
                        <Box sx={{ m: 2 }}>
                            <Typography variant="subtitle2" gutterBottom>
                                Metric Details
                            </Typography>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Principle</TableCell>
                                        <TableCell>Metric</TableCell>
                                        <TableCell align="right">Value</TableCell>
                                        <TableCell align="right">Threshold</TableCell>
                                        <TableCell>Status</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {results.map((r, idx) => (
                                        <TableRow key={idx}>
                                            <TableCell>
                                                <Chip
                                                    size="small"
                                                    label={r.principle}
                                                    color={principleChipColor(r.principle)}
                                                    variant="outlined"
                                                />
                                            </TableCell>
                                            <TableCell>{r.metric_name}</TableCell>
                                            <TableCell align="right">
                                                {r.metric_value !== null ? r.metric_value.toFixed(4) : '—'}
                                            </TableCell>
                                            <TableCell align="right">
                                                {r.threshold !== null ? r.threshold : '—'}
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    size="small"
                                                    label={r.passed ? 'Pass' : 'Fail'}
                                                    color={r.passed ? 'success' : 'error'}
                                                />
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>

                            {trace.status === 'fail' && trace.validation && onViewRootCause && (
                                <Box sx={{ mt: 1 }}>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        color="error"
                                        onClick={() => onViewRootCause(trace.validation!.id)}
                                    >
                                        View Root-Cause Analysis
                                    </Button>
                                </Box>
                            )}
                        </Box>
                    </Collapse>
                </TableCell>
            </TableRow>
        </>
    );
}

/* ---------- Main Component ---------- */
export default function TraceabilityMatrix({ traces, loading, onViewRootCause }: Props) {
    const [principleFilter, setPrincipleFilter] = useState<string>('all');
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [search, setSearch] = useState('');

    const filtered = useMemo(() => {
        return traces.filter((t) => {
            // Only show definitive outcomes in UI.
            if (t.status !== 'pass' && t.status !== 'fail') return false;

            // Principle filter
            if (principleFilter !== 'all') {
                const p = t.requirement?.principle ?? t.unlinked_principle ?? '';
                if (p !== principleFilter) return false;
            }
            // Status filter
            if (statusFilter !== 'all' && t.status !== statusFilter) return false;
            // Search
            if (search) {
                const s = search.toLowerCase();
                const haystack = [
                    t.requirement?.name,
                    t.requirement?.principle,
                    t.dataset?.name,
                    t.model?.name,
                ]
                    .filter(Boolean)
                    .join(' ')
                    .toLowerCase();
                if (!haystack.includes(s)) return false;
            }
            return true;
        });
    }, [traces, principleFilter, statusFilter, search]);

    /* CSV export */
    const handleExportCSV = () => {
        const header = [
            'Requirement',
            'Principle',
            'Dataset',
            'Model',
            'Metrics Passed',
            'Total Metrics',
            'Status',
            'Behavior Pattern',
        ];
        const rows = filtered.map((t) => {
            const results = t.validation?.results ?? [];
            return [
                t.requirement?.name ?? '',
                t.requirement?.principle ?? t.unlinked_principle ?? '',
                t.dataset?.name ?? '',
                t.model?.name ?? '',
                results.filter((r) => r.passed).length,
                results.length,
                t.status,
                (t.validation?.behavior_pattern ?? '').replace(/"/g, '""'),
            ];
        });

        const csv = [header.join(','), ...rows.map((r) => r.map((c) => `"${c}"`).join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'traceability_matrix.csv';
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <Box>
            {loading && <LinearProgress sx={{ mb: 1 }} />}

            {/* Filters */}
            <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }} flexWrap="wrap">
                <FilterIcon color="action" />
                <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel>Principle</InputLabel>
                    <Select
                        value={principleFilter}
                        label="Principle"
                        onChange={(e) => setPrincipleFilter(e.target.value)}
                    >
                        <MenuItem value="all">All Principles</MenuItem>
                        <MenuItem value="fairness">Fairness</MenuItem>
                        <MenuItem value="privacy">Privacy</MenuItem>
                        <MenuItem value="transparency">Transparency</MenuItem>
                        <MenuItem value="accountability">Accountability</MenuItem>
                    </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 140 }}>
                    <InputLabel>Status</InputLabel>
                    <Select
                        value={statusFilter}
                        label="Status"
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <MenuItem value="all">Pass + Fail</MenuItem>
                        <MenuItem value="pass">Pass</MenuItem>
                        <MenuItem value="fail">Fail</MenuItem>
                    </Select>
                </FormControl>
                <TextField
                    size="small"
                    placeholder="Search…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    sx={{ minWidth: 180 }}
                />
                <Box sx={{ flex: 1 }} />
                <Button
                    startIcon={<DownloadIcon />}
                    size="small"
                    variant="outlined"
                    onClick={handleExportCSV}
                >
                    Export CSV
                </Button>
            </Stack>

            {filtered.length === 0 && !loading ? (
                <Alert severity="info">
                    No traces match the current filters. Adjust filters or run validations to populate the matrix.
                </Alert>
            ) : (
                <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell padding="checkbox" />
                                <TableCell>Requirement</TableCell>
                                <TableCell>Dataset</TableCell>
                                <TableCell>Model</TableCell>
                                <TableCell>Validation Result</TableCell>
                                <TableCell>Status</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {filtered.map((trace, idx) => (
                                <TraceRow
                                    key={`${trace.requirement?.id ?? 'u'}-${trace.validation?.id ?? idx}`}
                                    trace={trace}
                                    onViewRootCause={onViewRootCause}
                                />
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}
        </Box>
    );
}
