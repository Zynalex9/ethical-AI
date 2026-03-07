// Template Browser Page – Phase 5 (6.3)
// Browse, filter, view details, and apply domain-specific ethical requirement templates.

import { useState } from 'react';
import {
    Box,
    Container,
    Typography,
    Button,
    Card,
    CardContent,
    CardActions,
    Grid,
    Chip,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    CircularProgress,
    Alert,
    Divider,
    InputAdornment,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
} from '@mui/material';
import {
    Search as SearchIcon,
    Gavel as LegalIcon,
    Rule as RuleIcon,
    LocalHospital as HealthIcon,
    AccountBalance as FinanceIcon,
    School as EducationIcon,
    Business as EmploymentIcon,
    Security as SecurityIcon,
    Public as PublicIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { templatesApi, projectsApi } from '../services/api';
import type { Template, Project, TemplateRuleItem } from '../types';
import TemplateCustomizer from '../components/TemplateCustomizer';


const DOMAIN_OPTIONS = [
    { value: '', label: 'All Domains' },
    { value: 'finance', label: 'Finance' },
    { value: 'healthcare', label: 'Healthcare' },
    { value: 'criminal_justice', label: 'Criminal Justice' },
    { value: 'employment', label: 'Employment' },
    { value: 'education', label: 'Education' },
    { value: 'general', label: 'General' },
];

const PRINCIPLE_OPTIONS = [
    { value: '', label: 'All Principles' },
    { value: 'fairness', label: 'Fairness' },
    { value: 'transparency', label: 'Transparency' },
    { value: 'privacy', label: 'Privacy' },
    { value: 'accountability', label: 'Accountability' },
];

const DOMAIN_ICONS: Record<string, React.ReactElement> = {
    finance: <FinanceIcon />,
    healthcare: <HealthIcon />,
    criminal_justice: <LegalIcon />,
    employment: <EmploymentIcon />,
    education: <EducationIcon />,
    general: <PublicIcon />,
};

const DOMAIN_COLORS: Record<string, 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info' | 'default'> = {
    finance: 'primary',
    healthcare: 'error',
    criminal_justice: 'warning',
    employment: 'info',
    education: 'success',
    general: 'default',
};

const PRINCIPLE_COLORS: Record<string, 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info' | 'default'> = {
    fairness: 'primary',
    transparency: 'info',
    privacy: 'warning',
    accountability: 'secondary',
};

export default function TemplateBrowserPage() {
    const queryClient = useQueryClient();

    // Filters
    const [domainFilter, setDomainFilter] = useState('');
    const [principleFilter, setPrincipleFilter] = useState('');
    const [searchQuery, setSearchQuery] = useState('');

    // Detail modal
    const [detailTemplate, setDetailTemplate] = useState<Template | null>(null);

    // Apply-to-project dialog
    const [applyTemplate, setApplyTemplate] = useState<Template | null>(null);
    const [selectedProjectId, setSelectedProjectId] = useState('');

    // Customizer
    const [customizeTemplate, setCustomizeTemplate] = useState<Template | null>(null);

    // Feedback
    const [successMsg, setSuccessMsg] = useState('');

    // Queries
    const { data: templates = [], isLoading } = useQuery<Template[]>({
        queryKey: ['templates', domainFilter, principleFilter, searchQuery],
        queryFn: () =>
            templatesApi.list({
                domain: domainFilter || undefined,
                principle: principleFilter || undefined,
                search: searchQuery || undefined,
            }),
    });

    const { data: projects = [] } = useQuery<Project[]>({
        queryKey: ['projects'],
        queryFn: projectsApi.list,
    });

    // Apply mutation
    const applyMutation = useMutation({
        mutationFn: templatesApi.applyToProject,
        onSuccess: (data) => {
            setSuccessMsg(`Created ${data.requirements?.length ?? 0} requirements from template`);
            setApplyTemplate(null);
            setSelectedProjectId('');
            queryClient.invalidateQueries({ queryKey: ['requirements'] });
        },
    });

    // Customise + apply mutation
    const customizeApplyMutation = useMutation({
        mutationFn: async (payload: { templateId: string; projectId: string; customizations: Record<string, any> }) => {
            return templatesApi.applyToProject({
                project_id: payload.projectId,
                template_id: payload.templateId,
                customizations: payload.customizations,
            });
        },
        onSuccess: (data) => {
            setSuccessMsg(`Created ${data.requirements?.length ?? 0} customised requirements`);
            setCustomizeTemplate(null);
            setSelectedProjectId('');
            queryClient.invalidateQueries({ queryKey: ['requirements'] });
        },
    });

    const handleApply = () => {
        if (!applyTemplate || !selectedProjectId) return;
        applyMutation.mutate({
            project_id: selectedProjectId,
            template_id: applyTemplate.id,
        });
    };

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 8 }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{ fontWeight: 700 }}>
                    Ethical Requirement Templates
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Browse domain-specific ethical standards and apply them to your projects with one click.
                </Typography>
            </Box>

            {successMsg && (
                <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMsg('')}>
                    {successMsg}
                </Alert>
            )}

            {/* Filter Section */}
            <Card sx={{ mb: 4, p: 2 }}>
                <Grid container spacing={2} alignItems="center">
                    <Grid size={{ xs: 12, sm: 4 }}>
                        <FormControl fullWidth size="small">
                            <InputLabel>Domain</InputLabel>
                            <Select
                                value={domainFilter}
                                label="Domain"
                                onChange={(e) => setDomainFilter(e.target.value)}
                            >
                                {DOMAIN_OPTIONS.map((opt) => (
                                    <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 4 }}>
                        <FormControl fullWidth size="small">
                            <InputLabel>Principle</InputLabel>
                            <Select
                                value={principleFilter}
                                label="Principle"
                                onChange={(e) => setPrincipleFilter(e.target.value)}
                            >
                                {PRINCIPLE_OPTIONS.map((opt) => (
                                    <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Grid>
                    <Grid size={{ xs: 12, sm: 4 }}>
                        <TextField
                            fullWidth
                            size="small"
                            placeholder="Search templates..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchIcon />
                                    </InputAdornment>
                                ),
                            }}
                        />
                    </Grid>
                </Grid>
            </Card>

            {/* Template Cards Grid */}
            <Grid container spacing={3}>
                {templates.map((template) => {
                    const rules = template.rules || { principles: [], reference: '', items: [] };
                    const principles: string[] = rules.principles || [];
                    const items: TemplateRuleItem[] = rules.items || [];
                    const reference = rules.reference || '';

                    return (
                        <Grid key={template.id} size={{ xs: 12, sm: 6, md: 4 }}>
                            <Card
                                sx={{
                                    height: '100%',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    transition: 'transform 0.2s, box-shadow 0.2s',
                                    '&:hover': {
                                        transform: 'translateY(-4px)',
                                        boxShadow: '0 8px 24px rgba(102, 126, 234, 0.2)',
                                    },
                                }}
                            >
                                <CardContent sx={{ flex: 1 }}>
                                    {/* Title row */}
                                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                        <Box
                                            sx={{
                                                width: 36,
                                                height: 36,
                                                borderRadius: 1,
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                bgcolor: 'action.hover',
                                                mr: 1.5,
                                                color: 'primary.main',
                                            }}
                                        >
                                            {DOMAIN_ICONS[template.domain] || <SecurityIcon />}
                                        </Box>
                                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                            {template.name}
                                        </Typography>
                                    </Box>

                                    {/* Badges */}
                                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1.5 }}>
                                        <Chip
                                            label={template.domain.replace('_', ' ')}
                                            size="small"
                                            color={DOMAIN_COLORS[template.domain] || 'default'}
                                            sx={{ textTransform: 'capitalize' }}
                                        />
                                        {principles.map((p) => (
                                            <Chip
                                                key={p}
                                                label={p}
                                                size="small"
                                                variant="outlined"
                                                color={PRINCIPLE_COLORS[p] || 'default'}
                                                sx={{ textTransform: 'capitalize' }}
                                            />
                                        ))}
                                    </Box>

                                    {/* Description */}
                                    <Typography
                                        variant="body2"
                                        color="text.secondary"
                                        sx={{
                                            mb: 1.5,
                                            display: '-webkit-box',
                                            WebkitLineClamp: 3,
                                            WebkitBoxOrient: 'vertical',
                                            overflow: 'hidden',
                                        }}
                                    >
                                        {template.description}
                                    </Typography>

                                    {/* Meta */}
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <Chip
                                            icon={<RuleIcon />}
                                            label={`${items.length} rule${items.length !== 1 ? 's' : ''}`}
                                            size="small"
                                            variant="outlined"
                                        />
                                        {reference && (
                                            <Typography variant="caption" color="text.disabled" noWrap sx={{ maxWidth: 140 }}>
                                                {reference}
                                            </Typography>
                                        )}
                                    </Box>
                                </CardContent>

                                <Divider />

                                <CardActions sx={{ justifyContent: 'space-between', px: 2 }}>
                                    <Button size="small" onClick={() => setDetailTemplate(template)}>
                                        View Details
                                    </Button>
                                    <Button
                                        size="small"
                                        variant="contained"
                                        onClick={() => {
                                            setApplyTemplate(template);
                                            setSelectedProjectId('');
                                        }}
                                    >
                                        Apply to Project
                                    </Button>
                                </CardActions>
                            </Card>
                        </Grid>
                    );
                })}

                {templates.length === 0 && (
                    <Grid size={{ xs: 12 }}>
                        <Box sx={{ textAlign: 'center', py: 8 }}>
                            <SecurityIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography variant="h6" color="text.secondary">
                                No templates found
                            </Typography>
                            <Typography variant="body2" color="text.disabled">
                                Try adjusting your filters or search query.
                            </Typography>
                        </Box>
                    </Grid>
                )}
            </Grid>

            {/* ─── Detail Modal ──────────────────────────────────────── */}
            <Dialog
                open={!!detailTemplate}
                onClose={() => setDetailTemplate(null)}
                maxWidth="md"
                fullWidth
            >
                {detailTemplate && (
                    <>
                        <DialogTitle>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                {DOMAIN_ICONS[detailTemplate.domain] || <SecurityIcon />}
                                {detailTemplate.name}
                            </Box>
                        </DialogTitle>
                        <DialogContent dividers>
                            <Typography variant="body1" sx={{ mb: 2 }}>
                                {detailTemplate.description}
                            </Typography>

                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 2 }}>
                                <Chip
                                    label={detailTemplate.domain.replace('_', ' ')}
                                    size="small"
                                    color={DOMAIN_COLORS[detailTemplate.domain] || 'default'}
                                    sx={{ textTransform: 'capitalize' }}
                                />
                                {(detailTemplate.rules?.principles || []).map((p: string) => (
                                    <Chip
                                        key={p}
                                        label={p}
                                        size="small"
                                        variant="outlined"
                                        color={PRINCIPLE_COLORS[p] || 'default'}
                                        sx={{ textTransform: 'capitalize' }}
                                    />
                                ))}
                            </Box>

                            {detailTemplate.rules?.reference && (
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                    <strong>Reference:</strong> {detailTemplate.rules.reference}
                                </Typography>
                            )}

                            <Typography variant="subtitle2" sx={{ mb: 1 }}>
                                Rules ({(detailTemplate.rules?.items || []).length})
                            </Typography>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Metric</TableCell>
                                            <TableCell>Operator</TableCell>
                                            <TableCell>Threshold</TableCell>
                                            <TableCell>Principle</TableCell>
                                            <TableCell>Description</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {(detailTemplate.rules?.items || []).map((item: TemplateRuleItem, idx: number) => (
                                            <TableRow key={idx}>
                                                <TableCell sx={{ fontFamily: 'monospace' }}>{item.metric}</TableCell>
                                                <TableCell>{item.operator}</TableCell>
                                                <TableCell>{item.value}</TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={item.principle || 'fairness'}
                                                        size="small"
                                                        variant="outlined"
                                                        sx={{ textTransform: 'capitalize' }}
                                                    />
                                                </TableCell>
                                                <TableCell>{item.description}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </DialogContent>
                        <DialogActions>
                            <Button onClick={() => setDetailTemplate(null)}>Close</Button>
                            <Button
                                variant="outlined"
                                onClick={() => {
                                    setCustomizeTemplate(detailTemplate);
                                    setDetailTemplate(null);
                                }}
                            >
                                Customize &amp; Apply
                            </Button>
                            <Button
                                variant="contained"
                                onClick={() => {
                                    setApplyTemplate(detailTemplate);
                                    setDetailTemplate(null);
                                    setSelectedProjectId('');
                                }}
                            >
                                Apply as-is
                            </Button>
                        </DialogActions>
                    </>
                )}
            </Dialog>

            {/* ─── Apply-to-Project Dialog ───────────────────────────── */}
            <Dialog
                open={!!applyTemplate}
                onClose={() => setApplyTemplate(null)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>Apply Template to Project</DialogTitle>
                <DialogContent>
                    {applyMutation.isError && (
                        <Alert severity="error" sx={{ mb: 2 }}>
                            Failed to apply template. Please try again.
                        </Alert>
                    )}
                    <Typography variant="body2" sx={{ mb: 2 }}>
                        Select which project should receive the requirements from{' '}
                        <strong>{applyTemplate?.name}</strong>.
                    </Typography>
                    <FormControl fullWidth>
                        <InputLabel>Project</InputLabel>
                        <Select
                            value={selectedProjectId}
                            label="Project"
                            onChange={(e) => setSelectedProjectId(e.target.value)}
                        >
                            {projects.map((p) => (
                                <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setApplyTemplate(null)}>Cancel</Button>
                    <Button
                        variant="contained"
                        disabled={!selectedProjectId || applyMutation.isPending}
                        onClick={handleApply}
                    >
                        {applyMutation.isPending ? <CircularProgress size={20} /> : 'Apply'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* ─── Customizer Dialog ─────────────────────────────────── */}
            {customizeTemplate && (
                <TemplateCustomizer
                    open
                    template={customizeTemplate}
                    projects={projects}
                    loading={customizeApplyMutation.isPending}
                    onClose={() => setCustomizeTemplate(null)}
                    onApply={(projectId: string, customizations: Record<string, any>) => {
                        customizeApplyMutation.mutate({
                            templateId: customizeTemplate.id,
                            projectId,
                            customizations,
                        });
                    }}
                />
            )}
        </Container>
    );
}
