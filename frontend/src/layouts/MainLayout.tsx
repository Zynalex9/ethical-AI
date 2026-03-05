// Main layout with sidebar navigation

import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
    Box,
    Drawer,
    AppBar,
    Toolbar,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Typography,
    IconButton,
    Avatar,
    Menu,
    MenuItem,
    Divider,
    useTheme,
    useMediaQuery,
} from '@mui/material';
import {
    Dashboard as DashboardIcon,
    Folder as FolderIcon,
    Assessment as AssessmentIcon,
    Description as DescriptionIcon,
    History as HistoryIcon,
    Settings as SettingsIcon,
    Menu as MenuIcon,
    Security as SecurityIcon,
    Logout as LogoutIcon,
    Person as PersonIcon,
    AdminPanelSettings as AdminIcon,
    MenuBook as KnowledgeIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import NotificationBell from '../components/NotificationBell';

const DRAWER_WIDTH = 260;

const menuItems = [
    { text: 'Dashboard', icon: DashboardIcon, path: '/dashboard' },
    { text: 'Projects', icon: FolderIcon, path: '/projects' },
    { text: 'Validations', icon: AssessmentIcon, path: '/validations' },
    { text: 'Templates', icon: DescriptionIcon, path: '/templates' },
    { text: 'Audit Log', icon: HistoryIcon, path: '/audit' },
    { text: 'Knowledge Base', icon: KnowledgeIcon, path: '/knowledge-base' },
    { text: 'Admin', icon: AdminIcon, path: '/admin', adminOnly: true },
];

export default function MainLayout() {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));
    const navigate = useNavigate();
    const location = useLocation();
    const { user, logout } = useAuth();

    const [mobileOpen, setMobileOpen] = useState(false);
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    const handleProfileMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleProfileMenuClose = () => {
        setAnchorEl(null);
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const drawer = (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Logo */}
            <Box sx={{ p: 3, display: 'flex', alignItems: 'center' }}>
                <Box
                    sx={{
                        width: 40,
                        height: 40,
                        borderRadius: 1.5,
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        mr: 1.5,
                    }}
                >
                    <SecurityIcon sx={{ color: 'white', fontSize: 24 }} />
                </Box>
                <Box>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                        Ethical AI
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        Platform
                    </Typography>
                </Box>
            </Box>

            <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)' }} />

            {/* Navigation */}
            <List sx={{ px: 2, flex: 1 }}>
                {menuItems
                    .filter((item) => !(item as any).adminOnly || user?.role === 'admin')
                    .map((item) => {
                    const isActive = location.pathname === item.path;
                    return (
                        <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
                            <ListItemButton
                                onClick={() => {
                                    navigate(item.path);
                                    if (isMobile) setMobileOpen(false);
                                }}
                                sx={{
                                    borderRadius: 2,
                                    backgroundColor: isActive ? 'rgba(102, 126, 234, 0.15)' : 'transparent',
                                    '&:hover': {
                                        backgroundColor: isActive
                                            ? 'rgba(102, 126, 234, 0.2)'
                                            : 'rgba(255, 255, 255, 0.05)',
                                    },
                                }}
                            >
                                <ListItemIcon
                                    sx={{
                                        minWidth: 40,
                                        color: isActive ? 'primary.main' : 'text.secondary',
                                    }}
                                >
                                    <item.icon />
                                </ListItemIcon>
                                <ListItemText
                                    primary={item.text}
                                    primaryTypographyProps={{
                                        fontWeight: isActive ? 600 : 400,
                                        color: isActive ? 'text.primary' : 'text.secondary',
                                    }}
                                />
                            </ListItemButton>
                        </ListItem>
                    );
                })}
            </List>

            {/* User Info */}
            <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)' }} />
            <Box sx={{ p: 2 }}>
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        p: 1.5,
                        borderRadius: 2,
                        backgroundColor: 'rgba(255, 255, 255, 0.03)',
                    }}
                >
                    <Avatar
                        sx={{
                            width: 36,
                            height: 36,
                            bgcolor: 'primary.main',
                            fontSize: '0.875rem',
                        }}
                    >
                        {user?.name?.charAt(0) || 'U'}
                    </Avatar>
                    <Box sx={{ ml: 1.5, overflow: 'hidden' }}>
                        <Typography variant="body2" sx={{ fontWeight: 500 }} noWrap>
                            {user?.name || 'User'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" noWrap>
                            {user?.role || 'user'}
                        </Typography>
                    </Box>
                </Box>
            </Box>
        </Box>
    );

    return (
        <Box sx={{ display: 'flex', minHeight: '100vh' }}>
            {/* App Bar */}
            <AppBar
                position="fixed"
                sx={{
                    width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
                    ml: { md: `${DRAWER_WIDTH}px` },
                }}
            >
                <Toolbar>
                    <IconButton
                        color="inherit"
                        edge="start"
                        onClick={handleDrawerToggle}
                        sx={{ mr: 2, display: { md: 'none' } }}
                    >
                        <MenuIcon />
                    </IconButton>

                    <Box sx={{ flexGrow: 1 }} />

                    <NotificationBell />

                    <IconButton
                        onClick={handleProfileMenuOpen}
                        sx={{ p: 0 }}
                    >
                        <Avatar
                            sx={{
                                width: 36,
                                height: 36,
                                bgcolor: 'primary.main',
                            }}
                        >
                            {user?.name?.charAt(0) || 'U'}
                        </Avatar>
                    </IconButton>

                    <Menu
                        anchorEl={anchorEl}
                        open={Boolean(anchorEl)}
                        onClose={handleProfileMenuClose}
                        PaperProps={{
                            sx: {
                                mt: 1.5,
                                minWidth: 180,
                            },
                        }}
                    >
                        <MenuItem onClick={() => { handleProfileMenuClose(); navigate('/profile'); }}>
                            <ListItemIcon>
                                <PersonIcon fontSize="small" />
                            </ListItemIcon>
                            Profile
                        </MenuItem>
                        <MenuItem onClick={() => { handleProfileMenuClose(); navigate('/settings'); }}>
                            <ListItemIcon>
                                <SettingsIcon fontSize="small" />
                            </ListItemIcon>
                            Settings
                        </MenuItem>
                        <Divider />
                        <MenuItem onClick={handleLogout}>
                            <ListItemIcon>
                                <LogoutIcon fontSize="small" />
                            </ListItemIcon>
                            Logout
                        </MenuItem>
                    </Menu>
                </Toolbar>
            </AppBar>

            {/* Sidebar */}
            <Box
                component="nav"
                sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}
            >
                {/* Mobile drawer */}
                <Drawer
                    variant="temporary"
                    open={mobileOpen}
                    onClose={handleDrawerToggle}
                    ModalProps={{ keepMounted: true }}
                    sx={{
                        display: { xs: 'block', md: 'none' },
                        '& .MuiDrawer-paper': {
                            boxSizing: 'border-box',
                            width: DRAWER_WIDTH,
                        },
                    }}
                >
                    {drawer}
                </Drawer>

                {/* Desktop drawer */}
                <Drawer
                    variant="permanent"
                    sx={{
                        display: { xs: 'none', md: 'block' },
                        '& .MuiDrawer-paper': {
                            boxSizing: 'border-box',
                            width: DRAWER_WIDTH,
                        },
                    }}
                    open
                >
                    {drawer}
                </Drawer>
            </Box>

            {/* Main Content */}
            <Box
                component="main"
                sx={{
                    flexGrow: 1,
                    width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
                    minHeight: '100vh',
                    pt: 8,
                }}
            >
                <Outlet />
            </Box>
        </Box>
    );
}
