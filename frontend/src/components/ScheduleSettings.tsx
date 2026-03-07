
import {
    Box,
    Card,
    CardContent,
    Typography,
    Switch,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Button,
    Alert,
    CircularProgress,
    Chip,
} from '@mui/material';
import {
    Schedule as ScheduleIcon,
    Delete as DeleteIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scheduledValidationApi } from '../services/api';

interface Props {
    projectId: string;
}

export default function ScheduleSettings({ projectId }: Props) {
    const queryClient = useQueryClient();

    const { data: schedule, isLoading, error } = useQuery({
        queryKey: ['schedule', projectId],
        queryFn: () => scheduledValidationApi.get(projectId),
        retry: false,
    });

    const createMutation = useMutation({
        mutationFn: (frequency: string) =>
            scheduledValidationApi.create({ project_id: projectId, frequency }),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedule', projectId] }),
    });

    const updateMutation = useMutation({
        mutationFn: (data: { enabled?: boolean; frequency?: string }) =>
            scheduledValidationApi.update(projectId, data),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedule', projectId] }),
    });

    const deleteMutation = useMutation({
        mutationFn: () => scheduledValidationApi.delete(projectId),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedule', projectId] }),
    });

    if (isLoading) return <CircularProgress size={20} />;

    const hasSchedule = schedule && !error;

    return (
        <Card variant="outlined" sx={{ mb: 3 }}>
            <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <ScheduleIcon color="primary" />
                    <Typography variant="subtitle1" fontWeight={600}>
                        Scheduled Re-Validation
                    </Typography>
                </Box>

                {!hasSchedule ? (
                    <Box>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            Automatically re-run validations on a regular schedule to detect regressions.
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            {['daily', 'weekly', 'monthly'].map((freq) => (
                                <Button
                                    key={freq}
                                    variant="outlined"
                                    size="small"
                                    onClick={() => createMutation.mutate(freq)}
                                    disabled={createMutation.isPending}
                                >
                                    Enable {freq}
                                </Button>
                            ))}
                        </Box>
                    </Box>
                ) : (
                    <Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                            <Switch
                                checked={schedule.enabled}
                                onChange={(_, checked) => updateMutation.mutate({ enabled: checked })}
                            />
                            <Typography variant="body2">
                                {schedule.enabled ? 'Active' : 'Paused'}
                            </Typography>
                            <FormControl size="small" sx={{ minWidth: 120 }}>
                                <InputLabel>Frequency</InputLabel>
                                <Select
                                    value={schedule.frequency}
                                    label="Frequency"
                                    onChange={(e) => updateMutation.mutate({ frequency: e.target.value })}
                                >
                                    <MenuItem value="daily">Daily</MenuItem>
                                    <MenuItem value="weekly">Weekly</MenuItem>
                                    <MenuItem value="monthly">Monthly</MenuItem>
                                </Select>
                            </FormControl>
                            <Box sx={{ flex: 1 }} />
                            <Button
                                color="error"
                                size="small"
                                startIcon={<DeleteIcon />}
                                onClick={() => deleteMutation.mutate()}
                            >
                                Remove
                            </Button>
                        </Box>

                        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                            {schedule.last_run_at && (
                                <Chip
                                    label={`Last run: ${new Date(schedule.last_run_at).toLocaleString()}`}
                                    size="small"
                                    variant="outlined"
                                />
                            )}
                            {schedule.next_run_at && (
                                <Chip
                                    label={`Next run: ${new Date(schedule.next_run_at).toLocaleString()}`}
                                    size="small"
                                    color="primary"
                                    variant="outlined"
                                />
                            )}
                        </Box>

                        {updateMutation.isError && (
                            <Alert severity="error" sx={{ mt: 1 }}>Failed to update schedule</Alert>
                        )}
                    </Box>
                )}
            </CardContent>
        </Card>
    );
}
