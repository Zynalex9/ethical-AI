
import {
    Box,
    Card,
    CardContent,
    Typography,
    Checkbox,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Button,
    Chip,
    LinearProgress,
    Alert,
    CircularProgress,
    Link,
    Accordion,
    AccordionSummary,
    AccordionDetails,
} from '@mui/material';
import {
    ExpandMore as ExpandMoreIcon,
    PlaylistAddCheck as ChecklistIcon,
    CheckCircle as DoneIcon,
    RadioButtonUnchecked as UndoneIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { remediationApi } from '../services/api';
import type { RemediationChecklist } from '../types';

interface Props {
    suiteId: string;
}

const principleColors: Record<string, 'primary' | 'secondary' | 'warning' | 'info'> = {
    fairness: 'primary',
    privacy: 'warning',
    transparency: 'info',
    accountability: 'secondary',
};

const normalizeDocLink = (docLink?: string | null): string | null => {
    if (!docLink) return null;
    if (docLink.startsWith('/docs')) {
        return docLink.replace('/docs', '/knowledge-base');
    }
    return docLink;
};

export default function RemediationPanel({ suiteId }: Props) {
    const queryClient = useQueryClient();

    const { data, isLoading, error } = useQuery({
        queryKey: ['remediation', suiteId],
        queryFn: () => remediationApi.getChecklists(suiteId),
    });

    const generateMutation = useMutation({
        mutationFn: () => remediationApi.generate(suiteId),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['remediation', suiteId] }),
    });

    const stepMutation = useMutation({
        mutationFn: ({ checklistId, stepId, done }: { checklistId: string; stepId: string; done: boolean }) =>
            remediationApi.updateStep(checklistId, stepId, done),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['remediation', suiteId] }),
    });

    if (isLoading) return <CircularProgress size={24} />;
    if (error) return <Alert severity="error">Failed to load remediation checklists</Alert>;

    const checklists: RemediationChecklist[] = data?.checklists ?? [];

    if (checklists.length === 0) {
        return (
            <Card variant="outlined">
                <CardContent sx={{ textAlign: 'center', py: 4 }}>
                    <ChecklistIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                    <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
                        No remediation items are required for the current failed metrics.
                    </Typography>
                    <Button
                        variant="contained"
                        onClick={() => generateMutation.mutate()}
                        disabled={generateMutation.isPending}
                    >
                        Generate / Refresh From Latest Results
                    </Button>
                </CardContent>
            </Card>
        );
    }

    return (
        <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <ChecklistIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                    Guided Remediation
                </Typography>
            </Box>

            {checklists.map((cl) => {
                const doneCount = cl.steps.filter((s) => s.done).length;
                const total = cl.steps.length;
                const pct = total > 0 ? (doneCount / total) * 100 : 0;

                return (
                    <Accordion key={cl.id} defaultExpanded={!cl.all_done}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%', pr: 2 }}>
                                <Chip
                                    label={cl.principle}
                                    color={principleColors[cl.principle] || 'default'}
                                    size="small"
                                    sx={{ textTransform: 'capitalize', minWidth: 100 }}
                                />
                                <Box sx={{ flex: 1 }}>
                                    <LinearProgress
                                        variant="determinate"
                                        value={pct}
                                        color={cl.all_done ? 'success' : 'primary'}
                                        sx={{ height: 8, borderRadius: 4 }}
                                    />
                                </Box>
                                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 60, textAlign: 'right' }}>
                                    {doneCount}/{total}
                                </Typography>
                                {cl.all_done && <DoneIcon color="success" fontSize="small" />}
                            </Box>
                        </AccordionSummary>
                        <AccordionDetails sx={{ pt: 0 }}>
                            <List dense disablePadding>
                                {cl.steps.map((step) => {
                                    const resolvedDocLink = normalizeDocLink(step.doc_link);
                                    return (
                                    <ListItem
                                        key={step.id}
                                        disablePadding
                                        sx={{
                                            py: 0.5,
                                            opacity: step.done ? 0.6 : 1,
                                        }}
                                    >
                                        <ListItemIcon sx={{ minWidth: 36 }}>
                                            <Checkbox
                                                edge="start"
                                                checked={step.done}
                                                onChange={(_, checked) =>
                                                    stepMutation.mutate({ checklistId: cl.id, stepId: step.id, done: checked })
                                                }
                                                disabled={stepMutation.isPending}
                                                icon={<UndoneIcon />}
                                                checkedIcon={<DoneIcon color="success" />}
                                            />
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={step.description}
                                            primaryTypographyProps={{
                                                variant: 'body2',
                                                sx: { textDecoration: step.done ? 'line-through' : 'none' },
                                            }}
                                            secondary={
                                                resolvedDocLink ? (
                                                    <Link href={resolvedDocLink} target="_blank" rel="noopener" variant="caption">
                                                        Documentation
                                                    </Link>
                                                ) : undefined
                                            }
                                        />
                                    </ListItem>
                                    );
                                })}
                            </List>
                        </AccordionDetails>
                    </Accordion>
                );
            })}
        </Box>
    );
}
