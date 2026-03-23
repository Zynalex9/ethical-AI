import { useParams, useNavigate } from 'react-router-dom';
import {
    Container,
    Typography,
    Box,
    Card,
    CardContent,
    Button,
    Chip,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Alert,
    List,
    ListItem,
    ListItemText,
    CircularProgress,
    Divider
} from '@mui/material';
import {
    ArrowBack as ArrowBackIcon,
    Lock as LockIcon,
    CheckCircle as CheckIcon,
    Error as ErrorIcon,
    Warning as WarningIcon,
    Shield as ShieldIcon,
    Fingerprint as FingerprintIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { validationApi } from '../services/api';

// Type definitions for privacy validation response
interface PIIResult {
    column_name: string;
    is_pii: boolean;
    pii_type: string | null;
    confidence: number;
    sample_matches: string[];
    detection_method: string;
    details: string;
}



export default function PrivacyDetailPage() {
    const { validationId } = useParams<{ validationId: string }>();
    const navigate = useNavigate();

    // Use tanstack query to fetch privacy details with proper authentication
    const { data: privacyData, isLoading, error } = useQuery({
        queryKey: ['privacyDetails', validationId],
        queryFn: () => validationApi.getPrivacyDetails(validationId!),
        enabled: !!validationId,
        retry: 1,
    });

    if (isLoading) {
        return (
            <Container sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
                <CircularProgress />
            </Container>
        );
    }

    if (error || !privacyData) {
        return (
            <Container sx={{ mt: 4 }}>
                <Alert severity="error">
                    {error instanceof Error ? error.message : 'Failed to load privacy details'}
                </Alert>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
                    Go Back
                </Button>
            </Container>
        );
    }

    const piiDetected = privacyData.pii_results?.filter((pii: PIIResult) => pii.is_pii) || [];

    // Support both legacy and current HIPAA payload shapes from backend.
    const hipaaRows = (privacyData?.hipaa?.results || []).map((r: any) => {
        const identifier = r.label || r.identifier || r.identifier_id || 'Unknown';
        const flaggedColumns = r.flagged_columns || r.columns_flagged || [];
        const valueSamples = r.flagged_value_samples || [];
        const detail =
            r.detail ||
            r.description ||
            (valueSamples.length > 0
                ? `Examples: ${valueSamples.slice(0, 2).join(' | ')}`
                : 'No direct identifier evidence found.');

        return {
            ...r,
            identifier,
            flaggedColumns,
            detail,
        };
    });

    return (
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            {/* Header */}
            <Box sx={{ mb: 4 }}>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mb: 2 }}>
                    Back to Validation
                </Button>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <LockIcon sx={{ fontSize: 48, color: '#ff9800' }} />
                    <Box>
                        <Typography variant="h4">Privacy Validation Details</Typography>
                        <Typography variant="body2" color="text.secondary">
                            Validation ID: {validationId}
                        </Typography>
                    </Box>
                </Box>
            </Box>

            {/* Overall Status */}
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <Typography variant="h6">Overall Privacy Status</Typography>
                        <Chip
                            icon={privacyData.overall_passed ? <CheckIcon /> : <ErrorIcon />}
                            label={privacyData.overall_passed ? 'PASSED' : 'FAILED'}
                            color={privacyData.overall_passed ? 'success' : 'error'}
                            sx={{ fontSize: '1rem', py: 2 }}
                        />
                    </Box>
                </CardContent>
            </Card>

            {/* PII Detection Section */}
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                        {piiDetected.length === 0 ? <CheckIcon color="success" /> : <ErrorIcon color="error" />}
                        PII Detection Results
                    </Typography>
                    
                    {piiDetected.length === 0 ? (
                        <Alert severity="success">
                            ✓ No Personally Identifiable Information (PII) detected in the dataset
                        </Alert>
                    ) : (
                        <>
                            <Alert severity="error" sx={{ mb: 2 }}>
                                ⚠️ {piiDetected.length} column(s) contain PII that should be removed or anonymized
                            </Alert>
                            <TableContainer component={Paper} variant="outlined">
                                <Table>
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Column</TableCell>
                                            <TableCell>PII Type</TableCell>
                                            <TableCell>Confidence</TableCell>
                                            <TableCell>Detection Method</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {piiDetected.map((pii: PIIResult, idx: number) => (
                                            <TableRow key={idx}>
                                                <TableCell><strong>{pii.column_name}</strong></TableCell>
                                                <TableCell>
                                                    <Chip label={pii.pii_type} size="small" color="error" />
                                                </TableCell>
                                                <TableCell>{(pii.confidence * 100).toFixed(0)}%</TableCell>
                                                <TableCell>{pii.detection_method}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </>
                    )}
                </CardContent>
            </Card>

            {/* k-Anonymity Section — multi-config aware */}
            {(() => {
                // Prefer the full configs array (multi-config mode).
                // Fall back to the legacy single k_anonymity field.
                const configs: any[] =
                    privacyData.k_anonymity_configs?.length > 0
                        ? privacyData.k_anonymity_configs
                        : privacyData.k_anonymity
                        ? [privacyData.k_anonymity]
                        : [];

                if (configs.length === 0) return null;

                const isMulti = configs.length > 1;

                return (
                    <>
                        {isMulti && (
                            <Typography variant="h6" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                                k-Anonymity Configurations ({configs.length} configs)
                            </Typography>
                        )}
                        {configs.map((cfg: any, cfgIdx: number) => (
                            <Card key={cfgIdx} sx={{ mb: 2, border: cfg.satisfies_k ? '1px solid #4caf50' : '1px solid #f44336' }}>
                                <CardContent>
                                    <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                        {cfg.satisfies_k ? <CheckIcon color="success" /> : <ErrorIcon color="error" />}
                                        {isMulti ? `Config ${cfgIdx + 1} — k-Anonymity (k=${cfg.k_value})` : `k-Anonymity (k=${cfg.k_value})`}
                                    </Typography>

                                    <Box sx={{ mb: 2 }}>
                                        <Chip
                                            label={cfg.satisfies_k ? 'PASSED' : 'FAILED'}
                                            color={cfg.satisfies_k ? 'success' : 'error'}
                                            sx={{ mr: 2 }}
                                        />
                                        <Typography variant="body2" component="span" color="text.secondary">
                                            Ensures each combination of quasi-identifiers appears at least k times
                                        </Typography>
                                    </Box>

                                    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 2, mb: 2 }}>
                                        <Paper variant="outlined" sx={{ p: 2 }}>
                                            <Typography variant="caption" color="text.secondary">Required k</Typography>
                                            <Typography variant="h5">{cfg.k_value}</Typography>
                                        </Paper>
                                        <Paper variant="outlined" sx={{ p: 2 }}>
                                            <Typography variant="caption" color="text.secondary">Actual Min k</Typography>
                                            <Typography variant="h5" color={cfg.satisfies_k ? 'success.main' : 'error.main'}>
                                                {cfg.actual_min_k}
                                            </Typography>
                                        </Paper>
                                        <Paper variant="outlined" sx={{ p: 2 }}>
                                            <Typography variant="caption" color="text.secondary">Violating Groups</Typography>
                                            <Typography variant="h5" color={cfg.violating_groups_count > 0 ? 'error' : 'success.main'}>
                                                {cfg.violating_groups_count} / {cfg.total_groups}
                                            </Typography>
                                        </Paper>
                                    </Box>

                                    <Typography variant="subtitle2" sx={{ mb: 1 }}>
                                        Quasi-identifiers checked:
                                    </Typography>
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                                        {cfg.quasi_identifiers.map((qi: string) => (
                                            <Chip key={qi} label={qi} size="small" variant="outlined" />
                                        ))}
                                    </Box>

                                    {cfg.violating_groups?.length > 0 && (
                                        <>
                                            <Divider sx={{ my: 2 }} />
                                            <Typography variant="subtitle2" color="error" sx={{ mb: 1 }}>
                                                Sample Violating Groups (uniquely identifiable):
                                            </Typography>
                                            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 400 }}>
                                                <Table size="small">
                                                    <TableHead>
                                                        <TableRow>
                                                            {cfg.quasi_identifiers.map((qi: string) => (
                                                                <TableCell key={qi}>{qi}</TableCell>
                                                            ))}
                                                            <TableCell>Count</TableCell>
                                                        </TableRow>
                                                    </TableHead>
                                                    <TableBody>
                                                        {cfg.violating_groups.slice(0, 10).map((group: any, idx: number) => (
                                                            <TableRow key={idx}>
                                                                {cfg.quasi_identifiers.map((qi: string) => (
                                                                    <TableCell key={qi}>{String(group[qi])}</TableCell>
                                                                ))}
                                                                <TableCell>
                                                                    <Chip label={group.count} size="small" color="error" />
                                                                </TableCell>
                                                            </TableRow>
                                                        ))}
                                                    </TableBody>
                                                </Table>
                                            </TableContainer>
                                        </>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </>
                );
            })()}

            {/* l-Diversity Section */}
            {privacyData.l_diversity && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            {privacyData.l_diversity.satisfies_l ? <CheckIcon color="success" /> : <ErrorIcon color="error" />}
                            l-Diversity (l={privacyData.l_diversity.l_value})
                        </Typography>

                        <Box sx={{ mb: 2 }}>
                            <Chip
                                label={privacyData.l_diversity.satisfies_l ? 'PASSED' : 'FAILED'}
                                color={privacyData.l_diversity.satisfies_l ? 'success' : 'error'}
                                sx={{ mr: 2 }}
                            />
                            <Typography variant="body2" component="span" color="text.secondary">
                                Ensures each group has at least l distinct values of the sensitive attribute
                            </Typography>
                        </Box>

                        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 2, mb: 2 }}>
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Typography variant="caption" color="text.secondary">Required l</Typography>
                                <Typography variant="h5">{privacyData.l_diversity.l_value}</Typography>
                            </Paper>
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Typography variant="caption" color="text.secondary">Actual Min l</Typography>
                                <Typography variant="h5" color={privacyData.l_diversity.satisfies_l ? 'success.main' : 'error.main'}>
                                    {privacyData.l_diversity.actual_min_l}
                                </Typography>
                            </Paper>
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Typography variant="caption" color="text.secondary">Violating Groups</Typography>
                                <Typography variant="h5" color="error">
                                    {privacyData.l_diversity.violating_groups_count} / {privacyData.l_diversity.total_groups}
                                </Typography>
                            </Paper>
                        </Box>

                        <Alert severity="info" sx={{ mt: 2 }}>
                            <Typography variant="body2">
                                <strong>Sensitive Attribute:</strong> {privacyData.l_diversity.sensitive_attribute}
                            </Typography>
                            <Typography variant="caption">
                                Groups with only 1 distinct value in this column can be used to infer sensitive information
                            </Typography>
                        </Alert>
                    </CardContent>
                </Card>
            )}

            {/* Differential Privacy Section */}
            {privacyData.differential_privacy && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            {privacyData.differential_privacy.budget_satisfied ? <CheckIcon color="success" /> : <ErrorIcon color="error" />}
                            <FingerprintIcon />
                            Differential Privacy (ε)
                        </Typography>

                        <Box sx={{ mb: 2 }}>
                            <Chip
                                label={privacyData.differential_privacy.budget_satisfied ? 'BUDGET SATISFIED' : 'BUDGET EXCEEDED'}
                                color={privacyData.differential_privacy.budget_satisfied ? 'success' : 'error'}
                                sx={{ mr: 2 }}
                            />
                            {privacyData.differential_privacy.noise_applied && (
                                <Chip label="Noise Applied" color="info" variant="outlined" size="small" />
                            )}
                        </Box>

                        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 2, mb: 2 }}>
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Typography variant="caption" color="text.secondary">Measured ε</Typography>
                                <Typography variant="h5">{privacyData.differential_privacy.measured_epsilon?.toFixed(4)}</Typography>
                            </Paper>
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Typography variant="caption" color="text.secondary">Target ε</Typography>
                                <Typography variant="h5">{privacyData.differential_privacy.target_epsilon}</Typography>
                            </Paper>
                            <Paper variant="outlined" sx={{ p: 2 }}>
                                <Typography variant="caption" color="text.secondary">
                                    {privacyData.differential_privacy.noise_applied ? 'Post-Noise ε' : 'Status'}
                                </Typography>
                                <Typography variant="h5" color={privacyData.differential_privacy.budget_satisfied ? 'success.main' : 'error.main'}>
                                    {privacyData.differential_privacy.noise_applied
                                        ? privacyData.differential_privacy.noised_epsilon?.toFixed(4)
                                        : privacyData.differential_privacy.budget_satisfied ? '✓' : '✗'}
                                </Typography>
                            </Paper>
                        </Box>

                        {privacyData.differential_privacy.sensitivities && Object.keys(privacyData.differential_privacy.sensitivities).length > 0 && (
                            <>
                                <Typography variant="subtitle2" sx={{ mb: 1 }}>Column Sensitivities</Typography>
                                <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 300 }}>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Column</TableCell>
                                                <TableCell align="right">Sensitivity</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {Object.entries(privacyData.differential_privacy.sensitivities).map(([col, val]) => (
                                                <TableRow key={col}>
                                                    <TableCell>{col}</TableCell>
                                                    <TableCell align="right">{Number(val).toFixed(4)}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </>
                        )}

                        {privacyData.differential_privacy.details?.length > 0 && (
                            <Box sx={{ mt: 2 }}>
                                {privacyData.differential_privacy.details.map((d: string, idx: number) => (
                                    <Alert key={idx} severity="info" sx={{ mb: 0.5 }}>{d}</Alert>
                                ))}
                            </Box>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* HIPAA Safe Harbor Section */}
            {privacyData.hipaa && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            {privacyData.hipaa.overall_passed ? <CheckIcon color="success" /> : <ErrorIcon color="error" />}
                            <ShieldIcon />
                            HIPAA Safe Harbor De-Identification
                        </Typography>

                        <Box sx={{ mb: 2 }}>
                            <Chip
                                label={privacyData.hipaa.overall_passed ? 'COMPLIANT' : 'NON-COMPLIANT'}
                                color={privacyData.hipaa.overall_passed ? 'success' : 'error'}
                                sx={{ mr: 2 }}
                            />
                            <Typography variant="body2" component="span" color="text.secondary">
                                {privacyData.hipaa.passed_checks} / {privacyData.hipaa.total_checks} checks passed
                            </Typography>
                        </Box>

                        <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Identifier</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell>Flagged Columns</TableCell>
                                        <TableCell>Detail</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {hipaaRows.map((r: any, idx: number) => (
                                        <TableRow key={idx} sx={{ bgcolor: r.passed ? 'transparent' : 'error.900' }}>
                                            <TableCell sx={{ textTransform: 'capitalize' }}>
                                                {String(r.identifier).replace(/_/g, ' ')}
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={r.passed ? 'Pass' : 'Fail'}
                                                    color={r.passed ? 'success' : 'error'}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                {r.flaggedColumns?.length > 0
                                                    ? r.flaggedColumns.map((c: string) => (
                                                        <Chip key={c} label={c} size="small" variant="outlined" sx={{ mr: 0.5, mb: 0.5 }} />
                                                    ))
                                                    : '—'}
                                            </TableCell>
                                            <TableCell>
                                                <Typography variant="caption">{r.detail}</Typography>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </CardContent>
                </Card>
            )}

            {/* Recommendations Section */}
            {privacyData.recommendations && privacyData.recommendations.length > 0 && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <WarningIcon color="warning" />
                            Recommendations
                        </Typography>
                        <List>
                            {privacyData.recommendations.map((rec: string, idx: number) => (
                                <ListItem key={idx} sx={{ py: 0.5 }}>
                                    <ListItemText
                                        primary={rec}
                                        primaryTypographyProps={{
                                            variant: rec.startsWith('  →') ? 'body2' : 'body1',
                                            color: rec.startsWith('  →') ? 'text.secondary' : 'text.primary',
                                            sx: { fontFamily: 'monospace' }
                                        }}
                                    />
                                </ListItem>
                            ))}
                        </List>
                    </CardContent>
                </Card>
            )}

            {/* Warnings Section */}
            {privacyData.warnings && privacyData.warnings.length > 0 && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <WarningIcon color="warning" />
                            Warnings
                        </Typography>
                        {privacyData.warnings.map((warning: string, idx: number) => (
                            <Alert key={idx} severity="warning" sx={{ mb: 1 }}>
                                {warning}
                            </Alert>
                        ))}
                    </CardContent>
                </Card>
            )}
        </Container>
    );
}
