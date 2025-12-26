// Projects page - List and manage projects

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Box,
    Container,
    Typography,
    Button,
    Card,
    CardContent,
    CardActions,
    Grid,
    TextField,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    IconButton,
    Chip,
    CircularProgress,
    Alert,
} from '@mui/material';
import {
    Add as AddIcon,
    Folder as FolderIcon,
    Delete as DeleteIcon,
    Edit as EditIcon,
    ModelTraining as ModelIcon,
    Storage as DatasetIcon,
    Assignment as RequirementIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '../services/api';
import type { Project } from '../types';

export default function ProjectsPage() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    const [createOpen, setCreateOpen] = useState(false);
    const [newProject, setNewProject] = useState({ name: '', description: '' });
    const [error, setError] = useState('');

    // Fetch projects
    const { data: projects, isLoading } = useQuery<Project[]>({
        queryKey: ['projects'],
        queryFn: projectsApi.list,
    });

    // Create mutation
    const createMutation = useMutation({
        mutationFn: projectsApi.create,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['projects'] });
            setCreateOpen(false);
            setNewProject({ name: '', description: '' });
        },
        onError: (err: Error) => {
            setError(err.message || 'Failed to create project');
        },
    });

    // Delete mutation
    const deleteMutation = useMutation({
        mutationFn: projectsApi.delete,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['projects'] });
        },
    });

    const handleCreate = () => {
        if (!newProject.name.trim()) {
            setError('Project name is required');
            return;
        }
        createMutation.mutate(newProject);
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
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 700 }}>
                        Projects
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        Manage your AI validation projects
                    </Typography>
                </Box>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => setCreateOpen(true)}
                >
                    New Project
                </Button>
            </Box>

            {/* Projects Grid */}
            <Grid container spacing={3}>
                {projects?.map((project) => (
                    <Grid key={project.id} size={{ xs: 12, sm: 6, md: 4 }}>
                        <Card
                            sx={{
                                height: '100%',
                                display: 'flex',
                                flexDirection: 'column',
                                cursor: 'pointer',
                                transition: 'transform 0.2s, box-shadow 0.2s',
                                '&:hover': {
                                    transform: 'translateY(-4px)',
                                    boxShadow: '0 8px 24px rgba(102, 126, 234, 0.2)',
                                }
                            }}
                            onClick={() => navigate(`/projects/${project.id}`)}
                        >
                            <CardContent sx={{ flex: 1 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                    <Box
                                        sx={{
                                            width: 40,
                                            height: 40,
                                            borderRadius: 1,
                                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            mr: 1.5,
                                        }}
                                    >
                                        <FolderIcon sx={{ color: 'white' }} />
                                    </Box>
                                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                        {project.name}
                                    </Typography>
                                </Box>

                                <Typography
                                    variant="body2"
                                    color="text.secondary"
                                    sx={{
                                        mb: 2,
                                        display: '-webkit-box',
                                        WebkitLineClamp: 2,
                                        WebkitBoxOrient: 'vertical',
                                        overflow: 'hidden',
                                    }}
                                >
                                    {project.description || 'No description'}
                                </Typography>

                                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                    <Chip
                                        icon={<ModelIcon />}
                                        label={`${project.model_count || 0} Models`}
                                        size="small"
                                        variant="outlined"
                                    />
                                    <Chip
                                        icon={<DatasetIcon />}
                                        label={`${project.dataset_count || 0} Datasets`}
                                        size="small"
                                        variant="outlined"
                                    />
                                    <Chip
                                        icon={<RequirementIcon />}
                                        label={`${project.requirement_count || 0} Reqs`}
                                        size="small"
                                        variant="outlined"
                                    />
                                </Box>
                            </CardContent>

                            <CardActions sx={{ justifyContent: 'flex-end', px: 2, pb: 2 }}>
                                <IconButton
                                    size="small"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        // Edit functionality
                                    }}
                                >
                                    <EditIcon fontSize="small" />
                                </IconButton>
                                <IconButton
                                    size="small"
                                    color="error"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (confirm('Delete this project?')) {
                                            deleteMutation.mutate(project.id);
                                        }
                                    }}
                                >
                                    <DeleteIcon fontSize="small" />
                                </IconButton>
                            </CardActions>
                        </Card>
                    </Grid>
                ))}

                {/* Empty state */}
                {(!projects || projects.length === 0) && (
                    <Grid size={{ xs: 12 }}>
                        <Box
                            sx={{
                                textAlign: 'center',
                                py: 8,
                                px: 4,
                                borderRadius: 2,
                                border: '2px dashed',
                                borderColor: 'divider',
                            }}
                        >
                            <FolderIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                            <Typography variant="h6" color="text.secondary" gutterBottom>
                                No projects yet
                            </Typography>
                            <Typography variant="body2" color="text.disabled" sx={{ mb: 3 }}>
                                Create your first project to start validating AI models
                            </Typography>
                            <Button
                                variant="contained"
                                startIcon={<AddIcon />}
                                onClick={() => setCreateOpen(true)}
                            >
                                Create Project
                            </Button>
                        </Box>
                    </Grid>
                )}
            </Grid>

            {/* Create Dialog */}
            <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Create New Project</DialogTitle>
                <DialogContent>
                    {error && (
                        <Alert severity="error" sx={{ mb: 2 }}>
                            {error}
                        </Alert>
                    )}
                    <TextField
                        autoFocus
                        label="Project Name"
                        fullWidth
                        value={newProject.name}
                        onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                        sx={{ mt: 1, mb: 2 }}
                    />
                    <TextField
                        label="Description"
                        fullWidth
                        multiline
                        rows={3}
                        value={newProject.description}
                        onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
                    <Button
                        variant="contained"
                        onClick={handleCreate}
                        disabled={createMutation.isPending}
                    >
                        {createMutation.isPending ? <CircularProgress size={24} /> : 'Create'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
}
