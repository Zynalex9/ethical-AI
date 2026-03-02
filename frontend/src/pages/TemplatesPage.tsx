// Templates management page (admin / advanced users)

import { useState } from 'react';
import {
    Box,
    Container,
    Typography,
    Button,
    Card,
    CardContent,
    Grid,
    Chip,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    CircularProgress,
    Accordion,
    AccordionSummary,
    AccordionDetails,
} from '@mui/material';
import {
    Add as AddIcon,
    Delete as DeleteIcon,
    ExpandMore as ExpandIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { templatesApi } from '../services/api';
import type { Template, TemplateRuleItem } from '../types';

export default function TemplatesPage() {
    const queryClient = useQueryClient();
    const [createOpen, setCreateOpen] = useState(false);
    const [newTemplate, setNewTemplate] = useState({
        template_id: '',
        name: '',
        description: '',
        domain: 'general',
        rules: {
            principles: ['fairness'] as string[],
            reference: '',
            items: [{ metric: '', operator: '>=', value: 0.8, principle: 'fairness', description: '' }] as TemplateRuleItem[],
        },
    });

    const { data: templates, isLoading } = useQuery<Template[]>({
        queryKey: ['templates'],
        queryFn: () => templatesApi.list(),
    });

    const createMutation = useMutation({
        mutationFn: templatesApi.create,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['templates'] });
            setCreateOpen(false);
            setNewTemplate({
                template_id: '',
                name: '',
                description: '',
                domain: 'general',
                rules: {
                    principles: ['fairness'],
                    reference: '',
                    items: [{ metric: '', operator: '>=', value: 0.8, principle: 'fairness', description: '' }],
                },
            });
        },
    });

    const deleteMutation = useMutation({
        mutationFn: templatesApi.delete,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['templates'] });
        },
    });

    const addRule = () => {
        setNewTemplate({
            ...newTemplate,
            rules: {
                ...newTemplate.rules,
                items: [...newTemplate.rules.items, { metric: '', operator: '>=', value: 0.8, principle: 'fairness', description: '' }],
            },
        });
    };

    const updateRule = (index: number, field: string, value: any) => {
        const updated = [...newTemplate.rules.items];
        updated[index] = { ...updated[index], [field]: value };
        setNewTemplate({ ...newTemplate, rules: { ...newTemplate.rules, items: updated } });
    };

    const removeRule = (index: number) => {
        setNewTemplate({
            ...newTemplate,
            rules: {
                ...newTemplate.rules,
                items: newTemplate.rules.items.filter((_, i) => i !== index),
            },
        });
    };

    if (isLoading) return <CircularProgress sx={{ m: 4 }} />;

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 4 }}>
                <Typography variant="h4">Manage Templates</Typography>
                <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
                    New Template
                </Button>
            </Box>

            <Grid container spacing={3}>
                {templates?.map((template) => {
                    const rules = template.rules || { principles: [], reference: '', items: [] };
                    const principles: string[] = rules.principles || [];
                    const items: TemplateRuleItem[] = rules.items || [];
                    const isSystem = (template.template_id || '').startsWith('ETH') || (template.template_id || '').startsWith('GEN');
                    return (
                        <Grid key={template.id} size={{ xs: 12, md: 6 }}>
                            <Card>
                                <CardContent>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                                        <Typography variant="h6">{template.name}</Typography>
                                        <Box>
                                            <Chip label={template.domain.replace('_', ' ')} size="small" color="primary" sx={{ mr: 1, textTransform: 'capitalize' }} />
                                            {isSystem && <Chip label="System" size="small" />}
                                        </Box>
                                    </Box>

                                    {principles.length > 0 && (
                                        <Box sx={{ display: 'flex', gap: 0.5, mb: 1 }}>
                                            {principles.map((p) => (
                                                <Chip key={p} label={p} size="small" variant="outlined" sx={{ textTransform: 'capitalize' }} />
                                            ))}
                                        </Box>
                                    )}

                                    <Typography color="text.secondary" paragraph>
                                        {template.description}
                                    </Typography>

                                    <Accordion variant="outlined">
                                        <AccordionSummary expandIcon={<ExpandIcon />}>
                                            <Typography>{items.length} Rules</Typography>
                                        </AccordionSummary>
                                        <AccordionDetails>
                                            {items.map((rule, i) => (
                                                <Box key={i} sx={{ mb: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                                                    <Typography variant="subtitle2">{rule.metric}</Typography>
                                                    <Typography variant="body2" color="text.secondary">
                                                        {rule.operator} {rule.value} — {rule.description}
                                                    </Typography>
                                                </Box>
                                            ))}
                                        </AccordionDetails>
                                    </Accordion>

                                    {!isSystem && (
                                        <Box sx={{ mt: 2, textAlign: 'right' }}>
                                            <IconButton color="error" onClick={() => deleteMutation.mutate(template.id)}>
                                                <DeleteIcon />
                                            </IconButton>
                                        </Box>
                                    )}
                                </CardContent>
                            </Card>
                        </Grid>
                    );
                })}
            </Grid>

            <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="md" fullWidth>
                <DialogTitle>Create Template</DialogTitle>
                <DialogContent>
                    <Grid container spacing={2} sx={{ mt: 1 }}>
                        <Grid size={{ xs: 6 }}>
                            <TextField
                                fullWidth
                                label="Template ID (e.g. CUSTOM-001)"
                                value={newTemplate.template_id}
                                onChange={(e) => setNewTemplate({ ...newTemplate, template_id: e.target.value })}
                            />
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                            <TextField
                                fullWidth
                                label="Name"
                                value={newTemplate.name}
                                onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })}
                            />
                        </Grid>
                        <Grid size={{ xs: 12 }}>
                            <TextField
                                fullWidth
                                label="Description"
                                multiline
                                rows={2}
                                value={newTemplate.description}
                                onChange={(e) => setNewTemplate({ ...newTemplate, description: e.target.value })}
                            />
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                            <FormControl fullWidth>
                                <InputLabel>Domain</InputLabel>
                                <Select
                                    value={newTemplate.domain}
                                    label="Domain"
                                    onChange={(e) => setNewTemplate({ ...newTemplate, domain: e.target.value })}
                                >
                                    <MenuItem value="general">General</MenuItem>
                                    <MenuItem value="finance">Finance</MenuItem>
                                    <MenuItem value="healthcare">Healthcare</MenuItem>
                                    <MenuItem value="criminal_justice">Criminal Justice</MenuItem>
                                    <MenuItem value="employment">Employment</MenuItem>
                                    <MenuItem value="education">Education</MenuItem>
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                            <TextField
                                fullWidth
                                label="Legal Reference"
                                value={newTemplate.rules.reference}
                                onChange={(e) => setNewTemplate({ ...newTemplate, rules: { ...newTemplate.rules, reference: e.target.value } })}
                            />
                        </Grid>

                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle1" sx={{ mt: 2, mb: 1 }}>Rules</Typography>
                            {newTemplate.rules.items.map((rule, idx) => (
                                <Box key={idx} sx={{ display: 'flex', gap: 1, mb: 2 }}>
                                    <TextField
                                        label="Metric"
                                        size="small"
                                        value={rule.metric}
                                        onChange={(e) => updateRule(idx, 'metric', e.target.value)}
                                        sx={{ flex: 2 }}
                                    />
                                    <FormControl size="small" sx={{ width: 100 }}>
                                        <Select
                                            value={rule.operator}
                                            onChange={(e) => updateRule(idx, 'operator', e.target.value)}
                                        >
                                            <MenuItem value=">=">&ge;</MenuItem>
                                            <MenuItem value="<=">&le;</MenuItem>
                                            <MenuItem value="==">=</MenuItem>
                                        </Select>
                                    </FormControl>
                                    <TextField
                                        label="Value"
                                        size="small"
                                        type="number"
                                        value={rule.value}
                                        onChange={(e) => updateRule(idx, 'value', parseFloat(e.target.value))}
                                        sx={{ width: 100 }}
                                    />
                                    <IconButton size="small" color="error" onClick={() => removeRule(idx)}>
                                        <DeleteIcon />
                                    </IconButton>
                                </Box>
                            ))}
                            <Button size="small" startIcon={<AddIcon />} onClick={addRule}>
                                Add Rule
                            </Button>
                        </Grid>
                    </Grid>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={() => createMutation.mutate(newTemplate)}>
                        Create
                    </Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
}
