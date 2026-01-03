// Dashboard page with project overview

import { useMemo } from 'react';
import {
    Box,
    Container,
    Grid,
    Card,
    CardContent,
    Typography,
    Button,
    Chip,
    LinearProgress,
    CircularProgress,
} from '@mui/material';
import {
    Add as AddIcon,
    Folder as FolderIcon,
    Assessment as AssessmentIcon,
    CheckCircle as CheckCircleIcon,
    Warning as WarningIcon,
    TrendingUp as TrendingUpIcon,
    Schedule as ScheduleIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { projectsApi } from '../services/api';

// Stat card component
function StatCard({
    title,
    value,
    icon: Icon,
    color,
    trend
}: {
    title: string;
    value: string | number;
    icon: React.ElementType;
    color: string;
    trend?: string;
}) {
    return (
        <Card sx={{ height: '100%' }}>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <Box>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                            {title}
                        </Typography>
                        <Typography variant="h4" sx={{ fontWeight: 700 }}>
                            {value}
                        </Typography>
                        {trend && (
                            <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                                <TrendingUpIcon sx={{ fontSize: 16, color: 'success.main', mr: 0.5 }} />
                                <Typography variant="caption" color="success.main">
                                    {trend}
                                </Typography>
                            </Box>
                        )}
                    </Box>
                    <Box
                        sx={{
                            width: 48,
                            height: 48,
                            borderRadius: 2,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: `linear-gradient(135deg, ${color}22 0%, ${color}44 100%)`,
                        }}
                    >
                        <Icon sx={{ color }} />
                    </Box>
                </Box>
            </CardContent>
        </Card>
    );
}

// Recent project card
function ProjectCard({ project, onClick }: { 
    project: { 
        id: string;
        name: string; 
        status: string; 
        progress: number; 
        lastUpdated: string;
        modelCount: number;
        datasetCount: number;
    }; 
    onClick: () => void;
}) {
    return (
        <Card sx={{ mb: 2, cursor: 'pointer', '&:hover': { boxShadow: 6 } }} onClick={onClick}>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <FolderIcon sx={{ mr: 1.5, color: 'primary.main' }} />
                        <Typography variant="h6">{project.name}</Typography>
                    </Box>
                    <Chip
                        size="small"
                        label={project.status}
                        color={project.status === 'Ready' ? 'success' : project.status === 'In Progress' ? 'warning' : 'default'}
                    />
                </Box>
                <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                    <Chip
                        size="small"
                        label={`${project.modelCount} Model${project.modelCount !== 1 ? 's' : ''}`}
                        variant="outlined"
                    />
                    <Chip
                        size="small"
                        label={`${project.datasetCount} Dataset${project.datasetCount !== 1 ? 's' : ''}`}
                        variant="outlined"
                    />
                </Box>
                <Box sx={{ mb: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                            Setup Progress
                        </Typography>
                        <Typography variant="body2">{project.progress}%</Typography>
                    </Box>
                    <LinearProgress
                        variant="determinate"
                        value={project.progress}
                        sx={{
                            height: 6,
                            borderRadius: 3,
                            bgcolor: 'rgba(255,255,255,0.1)',
                            '& .MuiLinearProgress-bar': {
                                borderRadius: 3,
                                background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)',
                            },
                        }}
                    />
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <ScheduleIcon sx={{ fontSize: 14, color: 'text.secondary', mr: 0.5 }} />
                    <Typography variant="caption" color="text.secondary">
                        Updated {project.lastUpdated}
                    </Typography>
                </Box>
            </CardContent>
        </Card>
    );
}

export default function DashboardPage() {
    const { user } = useAuth();
    const navigate = useNavigate();

    // Fetch all projects for the user
    const { data: projects, isLoading: projectsLoading } = useQuery({
        queryKey: ['projects'],
        queryFn: () => projectsApi.list(),
    });

    // Calculate stats from real data
    const stats = useMemo(() => {
        if (!projects) return [];

        const totalProjects = projects.length;
        
        // Count models and datasets across all projects
        let totalModels = 0;
        let totalDatasets = 0;
        let totalValidations = 0;
        
        projects.forEach((project: any) => {
            totalModels += project.model_count || 0;
            totalDatasets += project.dataset_count || 0;
            totalValidations += project.validation_count || 0;
            // Assuming we have passed/failed counts
        });

        return [
            { title: 'Total Projects', value: totalProjects, icon: FolderIcon, color: '#667eea' },
            { title: 'Models & Datasets', value: totalModels + totalDatasets, icon: AssessmentIcon, color: '#764ba2' },
            { title: 'Active Projects', value: projects.filter((p: any) => !p.deleted_at).length, icon: CheckCircleIcon, color: '#4caf50' },
            { title: 'Total Assets', value: totalModels + totalDatasets, icon: WarningIcon, color: '#ff9800' },
        ];
    }, [projects]);

    // Get recent projects (last 3)
    const recentProjects = useMemo(() => {
        if (!projects || projects.length === 0) return [];
        
        return projects
            .slice(0, 3)
            .map((project: any) => {
                const modelCount = project.model_count || 0;
                const datasetCount = project.dataset_count || 0;
                
                // Calculate progress based on assets
                let progress = 0;
                let status = 'Not Started';
                
                if (modelCount > 0 && datasetCount > 0) {
                    progress = 100;
                    status = 'Ready';
                } else if (modelCount > 0 || datasetCount > 0) {
                    progress = 50;
                    status = 'In Progress';
                }
                
                // Format last updated
                const updatedDate = new Date(project.updated_at);
                const now = new Date();
                const diffMs = now.getTime() - updatedDate.getTime();
                const diffMins = Math.floor(diffMs / 60000);
                const diffHours = Math.floor(diffMs / 3600000);
                const diffDays = Math.floor(diffMs / 86400000);
                
                let lastUpdated = '';
                if (diffMins < 60) {
                    lastUpdated = `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
                } else if (diffHours < 24) {
                    lastUpdated = `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
                } else {
                    lastUpdated = `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
                }
                
                return {
                    id: project.id,
                    name: project.name,
                    status,
                    progress,
                    lastUpdated,
                    modelCount,
                    datasetCount,
                };
            });
    }, [projects]);

    if (projectsLoading) {
        return (
            <Container maxWidth="xl" sx={{ py: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
                <CircularProgress />
            </Container>
        );
    }

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Box>
                    <Typography variant="h4" sx={{ fontWeight: 700 }}>
                        Welcome back, {user?.name || 'User'}
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                        Here's what's happening with your AI validations
                    </Typography>
                </Box>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    sx={{ px: 3 }}
                    onClick={() => navigate('/projects')}
                >
                    New Project
                </Button>
            </Box>

            {/* Stats Grid */}
            <Grid container spacing={3} sx={{ mb: 4 }}>
                {stats.map((stat) => (
                    <Grid key={stat.title} size={{ xs: 12, sm: 6, md: 3 }}>
                        <StatCard {...stat} />
                    </Grid>
                ))}
            </Grid>

            {/* Main Content */}
            <Grid container spacing={3}>
                {/* Recent Projects */}
                <Grid size={{ xs: 12, md: 8 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                            Recent Projects
                        </Typography>
                        <Button size="small" onClick={() => navigate('/projects')}>View All</Button>
                    </Box>
                    {recentProjects.length === 0 ? (
                        <Card>
                            <CardContent sx={{ textAlign: 'center', py: 6 }}>
                                <FolderIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                                <Typography variant="h6" color="text.secondary" gutterBottom>
                                    No projects yet
                                </Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                                    Create your first project to start validating AI models
                                </Typography>
                                <Button
                                    variant="contained"
                                    startIcon={<AddIcon />}
                                    onClick={() => navigate('/projects')}
                                >
                                    Create Project
                                </Button>
                            </CardContent>
                        </Card>
                    ) : (
                        recentProjects.map((project:any) => (
                            <ProjectCard 
                                key={project.id} 
                                project={project}
                                onClick={() => navigate(`/projects/${project.id}`)}
                            />
                        ))
                    )}
                </Grid>

                {/* Quick Actions */}
                <Grid size={{ xs: 12, md: 4 }}>
                    <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                        Quick Actions
                    </Typography>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <Button variant="outlined" fullWidth startIcon={<AddIcon />} onClick={() => navigate('/projects')}>
                                    Upload New Model
                                </Button>
                                <Button variant="outlined" fullWidth startIcon={<AddIcon />} onClick={() => navigate('/projects')}>
                                    Upload Dataset
                                </Button>
                                <Button variant="outlined" fullWidth startIcon={<AssessmentIcon />} onClick={() => navigate('/validations')}>
                                    Run Validation
                                </Button>
                                <Button variant="outlined" fullWidth startIcon={<FolderIcon />} onClick={() => navigate('/templates')}>
                                    View Templates
                                </Button>
                            </Box>
                        </CardContent>
                    </Card>

                    {/* Getting Started Info */}
                    <Typography variant="h6" sx={{ fontWeight: 600, mt: 3, mb: 2 }}>
                        Ethical AI Principles
                    </Typography>
                    <Card>
                        <CardContent>
                            {[
                                { name: 'Fairness', icon: '⚖️', description: 'Ensure models treat all groups equitably' },
                                { name: 'Transparency', icon: '🔍', description: 'Make model decisions explainable' },
                                { name: 'Privacy', icon: '🔒', description: 'Protect sensitive personal information' },
                                { name: 'Accountability', icon: '📋', description: 'Track and audit all validations' },
                            ].map((principle) => (
                                <Box key={principle.name} sx={{ mb: 2, '&:last-child': { mb: 0 } }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                                        <Typography sx={{ fontSize: '1.2rem', mr: 1 }}>{principle.icon}</Typography>
                                        <Typography variant="body2" fontWeight={600}>{principle.name}</Typography>
                                    </Box>
                                    <Typography variant="caption" color="text.secondary">
                                        {principle.description}
                                    </Typography>
                                </Box>
                            ))}
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </Container>
    );
}
