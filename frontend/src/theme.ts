import { createTheme } from '@mui/material/styles';

// Custom dark theme for Ethical AI Platform
export const theme = createTheme({
    palette: {
        mode: 'dark',
        primary: {
            main: '#667eea',
            light: '#8fa4f5',
            dark: '#4c5fd7',
            contrastText: '#ffffff',
        },
        secondary: {
            main: '#764ba2',
            light: '#9b6fc4',
            dark: '#5a3380',
            contrastText: '#ffffff',
        },
        success: {
            main: '#4caf50',
            light: '#81c784',
            dark: '#388e3c',
        },
        error: {
            main: '#f44336',
            light: '#e57373',
            dark: '#d32f2f',
        },
        warning: {
            main: '#ff9800',
            light: '#ffb74d',
            dark: '#f57c00',
        },
        info: {
            main: '#2196f3',
            light: '#64b5f6',
            dark: '#1976d2',
        },
        background: {
            default: '#0a0a0f',
            paper: '#12121a',
        },
        text: {
            primary: 'rgba(255, 255, 255, 0.95)',
            secondary: 'rgba(255, 255, 255, 0.7)',
            disabled: 'rgba(255, 255, 255, 0.5)',
        },
        divider: 'rgba(255, 255, 255, 0.12)',
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
                        boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
                    },
                },
                contained: {
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    '&:hover': {
                        background: 'linear-gradient(135deg, #7b8ff0 0%, #8a5eb5 100%)',
                    },
                },
            },
        },
        MuiCard: {
            styleOverrides: {
                root: {
                    background: 'linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
                    backdropFilter: 'blur(10px)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
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
                            borderColor: 'rgba(255, 255, 255, 0.15)',
                        },
                        '&:hover fieldset': {
                            borderColor: 'rgba(255, 255, 255, 0.3)',
                        },
                        '&.Mui-focused fieldset': {
                            borderColor: '#667eea',
                        },
                    },
                },
            },
        },
        MuiAppBar: {
            styleOverrides: {
                root: {
                    background: 'rgba(10, 10, 15, 0.8)',
                    backdropFilter: 'blur(10px)',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                    boxShadow: 'none',
                },
            },
        },
        MuiDrawer: {
            styleOverrides: {
                paper: {
                    background: '#0d0d14',
                    borderRight: '1px solid rgba(255, 255, 255, 0.08)',
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
