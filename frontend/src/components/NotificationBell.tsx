import React, { useState } from 'react';
import {
    IconButton,
    Badge,
    Popover,
    Box,
    Typography,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Button,
    Divider,
    Chip,
} from '@mui/material';
import {
    Notifications as NotificationsIcon,
    Info as InfoIcon,
    Warning as WarningIcon,
    Error as ErrorIcon,
    CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '../services/api';
import type { Notification } from '../types';

const severityIcon: Record<string, React.ReactElement> = {
    info: <InfoIcon color="info" fontSize="small" />,
    warning: <WarningIcon color="warning" fontSize="small" />,
    error: <ErrorIcon color="error" fontSize="small" />,
    success: <SuccessIcon color="success" fontSize="small" />,
};

export default function NotificationBell() {
    const queryClient = useQueryClient();
    const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

    const { data } = useQuery({
        queryKey: ['notifications'],
        queryFn: () => notificationsApi.list(),
        refetchInterval: 30_000, // poll every 30 s
    });

    const markAllRead = useMutation({
        mutationFn: () => notificationsApi.markAllRead(),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
    });

    const markRead = useMutation({
        mutationFn: (ids: string[]) => notificationsApi.markRead(ids),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
    });

    const notifications: Notification[] = data?.notifications ?? [];
    const unreadCount = notifications.filter((n) => !n.read).length;

    const handleOpen = (e: React.MouseEvent<HTMLElement>) => setAnchorEl(e.currentTarget);
    const handleClose = () => setAnchorEl(null);

    const handleClickNotification = (n: Notification) => {
        if (!n.read) markRead.mutate([n.id]);
        if (n.link) window.location.href = n.link;
    };

    return (
        <>
            <IconButton color="inherit" onClick={handleOpen}>
                <Badge badgeContent={unreadCount} color="error">
                    <NotificationsIcon />
                </Badge>
            </IconButton>

            <Popover
                open={Boolean(anchorEl)}
                anchorEl={anchorEl}
                onClose={handleClose}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{ paper: { sx: { width: 380, maxHeight: 480 } } }}
            >
                <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="subtitle1" fontWeight={700}>
                        Notifications
                    </Typography>
                    {unreadCount > 0 && (
                        <Button size="small" onClick={() => markAllRead.mutate()}>
                            Mark all read
                        </Button>
                    )}
                </Box>
                <Divider />

                {notifications.length === 0 ? (
                    <Box sx={{ p: 3, textAlign: 'center' }}>
                        <Typography variant="body2" color="text.secondary">
                            No notifications yet
                        </Typography>
                    </Box>
                ) : (
                    <List dense sx={{ maxHeight: 380, overflow: 'auto', p: 0 }}>
                        {notifications.map((n) => (
                            <ListItem
                                key={n.id}
                                onClick={() => handleClickNotification(n)}
                                sx={{
                                    cursor: 'pointer',
                                    bgcolor: n.read ? 'transparent' : 'action.hover',
                                    borderLeft: n.read ? 'none' : '3px solid',
                                    borderColor: n.severity === 'error' ? 'error.main' : n.severity === 'warning' ? 'warning.main' : 'primary.main',
                                }}
                            >
                                <ListItemIcon sx={{ minWidth: 32 }}>
                                    {severityIcon[n.severity] || severityIcon.info}
                                </ListItemIcon>
                                <ListItemText
                                    primary={n.message}
                                    secondary={new Date(n.created_at).toLocaleString()}
                                    primaryTypographyProps={{ variant: 'body2', fontWeight: n.read ? 400 : 600 }}
                                    secondaryTypographyProps={{ variant: 'caption' }}
                                />
                                {!n.read && <Chip label="NEW" size="small" color="primary" sx={{ ml: 1 }} />}
                            </ListItem>
                        ))}
                    </List>
                )}
            </Popover>
        </>
    );
}
