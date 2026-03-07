// Admin Dashboard – system statistics, user management, health, and activity log

import { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Chip,
  IconButton,
  Select,
  MenuItem,
  Switch,
  Alert,
  CircularProgress,
  Paper,
  Tooltip,
} from '@mui/material';
import {
  People as PeopleIcon,
  Folder as FolderIcon,
  Assessment as AssessmentIcon,
  Storage as StorageIcon,
  CheckCircle as OkIcon,
  Cancel as ErrorIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';

// ── Types ──────────────────────────────────────────────────────────
interface SystemStats {
  total_users: number;
  total_projects: number;
  total_models: number;
  total_datasets: number;
  total_validations: number;
  validations_passed: number;
  validations_failed: number;
  validations_running: number;
}

interface UserRow {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

interface HealthStatus {
  database: string;
  redis: string;
  celery: string;
}

interface ActivityItem {
  id: string;
  action: string;
  resource_type: string;
  user_email: string | null;
  created_at: string;
}

// ── Stat Card ──────────────────────────────────────────────────────
function StatCard({ label, value, icon, color }: { label: string; value: number; icon: React.ReactNode; color: string }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: `${color}15`, color }}>
          {icon}
        </Box>
        <Box>
          <Typography variant="h5" fontWeight={700}>{value}</Typography>
          <Typography variant="body2" color="text.secondary">{label}</Typography>
        </Box>
      </CardContent>
    </Card>
  );
}

// ── Health Indicator ───────────────────────────────────────────────
function HealthChip({ label, status }: { label: string; status: string }) {
  const ok = status === 'ok';
  return (
    <Chip
      icon={ok ? <OkIcon /> : <ErrorIcon />}
      label={`${label}: ${status}`}
      color={ok ? 'success' : 'error'}
      variant="outlined"
      sx={{ mr: 1, mb: 1 }}
    />
  );
}

// ── Main Page ──────────────────────────────────────────────────────
export default function AdminDashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchAll = async () => {
    setLoading(true);
    setError('');
    try {
      const [statsRes, usersRes, healthRes, activityRes] = await Promise.all([
        api.get('/admin/stats'),
        api.get('/admin/users'),
        api.get('/admin/health'),
        api.get('/admin/activity?limit=15'),
      ]);
      setStats(statsRes.data);
      setUsers(usersRes.data);
      setHealth(healthRes.data);
      setActivity(activityRes.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load admin data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  // Guard: non-admin users
  if (user?.role !== 'admin') {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">Admin access required.</Alert>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  const handleRoleChange = async (userId: string, role: string) => {
    try {
      await api.patch(`/admin/users/${userId}/role`, { role });
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role } : u)));
    } catch {
      /* silently ignore – the server will reject invalid changes */
    }
  };

  const handleToggleActive = async (userId: string, isActive: boolean) => {
    try {
      await api.patch(`/admin/users/${userId}/status`, { is_active: isActive });
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, is_active: isActive } : u)));
    } catch {
      /* ignore */
    }
  };

  return (
    <Box sx={{ p: { xs: 2, md: 4 } }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4" fontWeight={700}>Admin Dashboard</Typography>
        <Tooltip title="Refresh">
          <IconButton onClick={fetchAll}><RefreshIcon /></IconButton>
        </Tooltip>
      </Box>

      {/* System Stats */}
      {stats && (
        <Grid container spacing={2} sx={{ mb: 4 }}>
          <Grid size={{ xs: 6, md: 3 }}><StatCard label="Users" value={stats.total_users} icon={<PeopleIcon />} color="#3f51b5" /></Grid>
          <Grid size={{ xs: 6, md: 3 }}><StatCard label="Projects" value={stats.total_projects} icon={<FolderIcon />} color="#009688" /></Grid>
          <Grid size={{ xs: 6, md: 3 }}><StatCard label="Validations" value={stats.total_validations} icon={<AssessmentIcon />} color="#ff9800" /></Grid>
          <Grid size={{ xs: 6, md: 3 }}><StatCard label="Models / Datasets" value={stats.total_models + stats.total_datasets} icon={<StorageIcon />} color="#e91e63" /></Grid>
        </Grid>
      )}

      {/* System Health */}
      {health && (
        <Paper sx={{ p: 2, mb: 4 }}>
          <Typography variant="h6" fontWeight={600} sx={{ mb: 1 }}>System Health</Typography>
          <HealthChip label="Database" status={health.database} />
          <HealthChip label="Redis" status={health.redis} />
          <HealthChip label="Celery" status={health.celery} />
        </Paper>
      )}

      {/* User Management */}
      <Paper sx={{ p: 2, mb: 4, overflowX: 'auto' }}>
        <Typography variant="h6" fontWeight={600} sx={{ mb: 1 }}>User Management</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Email</TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Active</TableCell>
              <TableCell>Joined</TableCell>
              <TableCell>Last Login</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id}>
                <TableCell>{u.email}</TableCell>
                <TableCell>{u.name}</TableCell>
                <TableCell>
                  <Select
                    size="small"
                    value={u.role}
                    onChange={(e) => handleRoleChange(u.id, e.target.value)}
                    disabled={u.id === user?.id}
                  >
                    <MenuItem value="user">user</MenuItem>
                    <MenuItem value="admin">admin</MenuItem>
                    <MenuItem value="auditor">auditor</MenuItem>
                  </Select>
                </TableCell>
                <TableCell>
                  <Switch
                    checked={u.is_active}
                    onChange={(e) => handleToggleActive(u.id, e.target.checked)}
                    disabled={u.id === user?.id}
                  />
                </TableCell>
                <TableCell>{new Date(u.created_at).toLocaleDateString()}</TableCell>
                <TableCell>{u.last_login ? new Date(u.last_login).toLocaleString() : '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      {/* Activity Log */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" fontWeight={600} sx={{ mb: 1 }}>Recent Activity</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Action</TableCell>
              <TableCell>Resource</TableCell>
              <TableCell>Time</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {activity.map((a) => (
              <TableRow key={a.id}>
                <TableCell>
                  <Chip label={a.action} size="small" variant="outlined" />
                </TableCell>
                <TableCell>{a.resource_type}</TableCell>
                <TableCell>{new Date(a.created_at).toLocaleString()}</TableCell>
              </TableRow>
            ))}
            {activity.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} align="center">No recent activity</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
