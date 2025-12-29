// Dashboard page with project overview

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
import { useAuth } from '../contexts/AuthContext';

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
function ProjectCard({ project }: { project: { name: string; status: string; progress: number; lastUpdated: string } }) {
    return (
        <Card sx={{ mb: 2 }}>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <FolderIcon sx={{ mr: 1.5, color: 'primary.main' }} />
                        <Typography variant="h6">{project.name}</Typography>
                    </Box>
                    <Chip
                        size="small"
                        label={project.status}
                        color={project.status === 'Passed' ? 'success' : project.status === 'In Progress' ? 'warning' : 'error'}
                    />
                </Box>
                <Box sx={{ mb: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="body2" color="text.secondary">
                            Validation Progress
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

    // Mock data for demo
    const stats = [
        { title: 'Total Projects', value: 12, icon: FolderIcon, color: '#667eea', trend: '+2 this month' },
        { title: 'Validations Run', value: 48, icon: AssessmentIcon, color: '#764ba2', trend: '+12 this week' },
        { title: 'Passed', value: 42, icon: CheckCircleIcon, color: '#4caf50' },
        { title: 'Needs Review', value: 6, icon: WarningIcon, color: '#ff9800' },
    ];

    const recentProjects = [
        { name: 'Credit Scoring Model v3', status: 'Passed', progress: 100, lastUpdated: '2 hours ago' },
        { name: 'Hiring Algorithm', status: 'In Progress', progress: 65, lastUpdated: '1 day ago' },
        { name: 'Healthcare Risk Assessment', status: 'Failed', progress: 100, lastUpdated: '3 days ago' },
    ];

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
                    {recentProjects.map((project) => (
                        <ProjectCard key={project.name} project={project} />
                    ))}
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

                    {/* Ethical Principles Summary */}
                    <Typography variant="h6" sx={{ fontWeight: 600, mt: 3, mb: 2 }}>
                        Validation Coverage
                    </Typography>
                    <Card>
                        <CardContent>
                            {[
                                { name: 'Fairness', count: 38, color: '#4caf50' },
                                { name: 'Transparency', count: 32, color: '#2196f3' },
                                { name: 'Privacy', count: 28, color: '#ff9800' },
                                { name: 'Accountability', count: 25, color: '#9c27b0' },
                            ].map((principle) => (
                                <Box key={principle.name} sx={{ mb: 2, '&:last-child': { mb: 0 } }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                        <Typography variant="body2">{principle.name}</Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            {principle.count} validations
                                        </Typography>
                                    </Box>
                                    <LinearProgress
                                        variant="determinate"
                                        value={(principle.count / 48) * 100}
                                        sx={{
                                            height: 4,
                                            borderRadius: 2,
                                            bgcolor: 'rgba(255,255,255,0.1)',
                                            '& .MuiLinearProgress-bar': {
                                                borderRadius: 2,
                                                bgcolor: principle.color,
                                            },
                                        }}
                                    />
                                </Box>
                            ))}
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </Container>
    );
}
