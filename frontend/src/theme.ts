import { createTheme } from '@mui/material/styles';

// Custom dark theme for Ethical AI Platform
export const theme = createTheme({
    palette: {
        mode: 'dark',
        primary: {
            main: '#3b82f6',
            light: '#60a5fa',
            dark: '#1d4ed8',
            contrastText: '#ffffff',
        },
        secondary: {
            main: '#14b8a6',
            light: '#2dd4bf',
            dark: '#0f766e',
            contrastText: '#ffffff',
        },
        success: {
            main: '#22c55e',
            light: '#4ade80',
            dark: '#15803d',
        },
        error: {
            main: '#ef4444',
            light: '#f87171',
            dark: '#b91c1c',
        },
        warning: {
            main: '#f59e0b',
            light: '#fbbf24',
            dark: '#b45309',
        },
        info: {
            main: '#0ea5e9',
            light: '#38bdf8',
            dark: '#0369a1',
        },
        background: {
            default: '#0b1220',
            paper: '#111a2e',
        },
        text: {
            primary: '#f8fafc',
            secondary: '#cbd5e1',
            disabled: '#94a3b8',
        },
        divider: 'rgba(148, 163, 184, 0.22)',
    },
    typography: {
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        h1: {
            fontSize: '2.5rem',
            fontWeight: 700,
            letterSpacing: '-0.02em',
        },
        h2: {
            fontSize: '2rem',
            fontWeight: 600,
            letterSpacing: '-0.01em',
        },
        h3: {
            fontSize: '1.5rem',
            fontWeight: 600,
        },
        h4: {
            fontSize: '1.25rem',
            fontWeight: 600,
        },
        h5: {
            fontSize: '1rem',
            fontWeight: 600,
        },
        h6: {
            fontSize: '0.875rem',
            fontWeight: 600,
        },
        body1: {
            fontSize: '1rem',
            lineHeight: 1.6,
        },
        body2: {
            fontSize: '0.875rem',
            lineHeight: 1.5,
        },
        button: {
            textTransform: 'none',
            fontWeight: 500,
        },
    },
    shape: {
        borderRadius: 12,
    },
    components: {
        MuiButton: {
            styleOverrides: {
                root: {
                    borderRadius: 8,
                    padding: '10px 24px',
                    fontWeight: 500,
                    boxShadow: 'none',
                    '&:hover': {
                        boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)',
                    },
                },
                contained: {
                    background: '#3b82f6',
                    '&:hover': {
                        background: '#2563eb',
                    },
                },
            },
        },
        MuiCard: {
            styleOverrides: {
                root: {
                    background: '#111a2e',
                    border: '1px solid rgba(148, 163, 184, 0.22)',
                    borderRadius: 16,
                },
            },
        },
        MuiPaper: {
            styleOverrides: {
                root: {
                    backgroundImage: 'none',
                },
            },
        },
        MuiTextField: {
            styleOverrides: {
                root: {
                    '& .MuiOutlinedInput-root': {
                        borderRadius: 8,
                        '& fieldset': {
                            borderColor: 'rgba(148, 163, 184, 0.35)',
                        },
                        '&:hover fieldset': {
                            borderColor: 'rgba(148, 163, 184, 0.55)',
                        },
                        '&.Mui-focused fieldset': {
                            borderColor: '#3b82f6',
                        },
                    },
                },
            },
        },
        MuiAppBar: {
            styleOverrides: {
                root: {
                    background: '#0f172a',
                    borderBottom: '1px solid rgba(148, 163, 184, 0.22)',
                    boxShadow: 'none',
                },
            },
        },
        MuiDrawer: {
            styleOverrides: {
                paper: {
                    background: '#0f172a',
                    borderRight: '1px solid rgba(148, 163, 184, 0.22)',
                },
            },
        },
        MuiChip: {
            styleOverrides: {
                root: {
                    borderRadius: 6,
                },
            },
        },
    },
});
