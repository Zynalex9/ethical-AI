// Quick Start Checklist — shows first-time users their progress through the platform setup

import {
  Box,
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Button,
  LinearProgress,
  Chip,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import { useNavigate } from 'react-router-dom';

interface ChecklistProps {
  /** Number of projects the user has */
  projectCount: number;
  /** Total models across all projects */
  modelCount: number;
  /** Total datasets across all projects */
  datasetCount: number;
  /** Total requirements created */
  requirementCount: number;
  /** Whether any validation has been run */
  hasValidations: boolean;
}

interface Step {
  label: string;
  done: boolean;
  route: string;
  tip: string;
}

export default function QuickStartChecklist({
  projectCount,
  modelCount,
  datasetCount,
  requirementCount,
  hasValidations,
}: ChecklistProps) {
  const navigate = useNavigate();

  const steps: Step[] = [
    {
      label: 'Create a project',
      done: projectCount > 0,
      route: '/projects',
      tip: 'Organise your work under a project',
    },
    {
      label: 'Upload an ML model',
      done: modelCount > 0,
      route: '/projects',
      tip: 'Supports sklearn, TensorFlow, PyTorch, ONNX',
    },
    {
      label: 'Upload or load a dataset',
      done: datasetCount > 0,
      route: '/projects',
      tip: 'CSV files or built-in benchmark datasets',
    },
    {
      label: 'Elicit ethical requirements',
      done: requirementCount > 0,
      route: '/projects',
      tip: 'Auto-generate from data or define manually',
    },
    {
      label: 'Run a validation',
      done: hasValidations,
      route: '/projects',
      tip: 'Test fairness, transparency, and privacy',
    },
  ];

  const completed = steps.filter((s) => s.done).length;
  const progress = Math.round((completed / steps.length) * 100);

  // Don't render if everything is already done
  if (completed === steps.length) return null;

  return (
    <Card
      sx={{
        mb: 3,
        border: '1px solid',
        borderColor: 'primary.dark',
        background: 'linear-gradient(135deg, rgba(59,130,246,0.05) 0%, rgba(20,184,166,0.05) 100%)',
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <RocketLaunchIcon color="primary" />
          <Typography variant="h6" fontWeight={700}>
            Quick Start
          </Typography>
          <Chip label={`${completed}/${steps.length}`} size="small" color="primary" variant="outlined" />
        </Box>

        <LinearProgress
          variant="determinate"
          value={progress}
          sx={{
            mb: 2,
            height: 6,
            borderRadius: 3,
            bgcolor: 'rgba(255,255,255,0.08)',
            '& .MuiLinearProgress-bar': {
              borderRadius: 3,
              background: 'linear-gradient(90deg, #3b82f6 0%, #14b8a6 100%)',
            },
          }}
        />

        <List dense disablePadding>
          {steps.map((step) => (
            <ListItem
              key={step.label}
              disablePadding
              sx={{ mb: 0.5 }}
              secondaryAction={
                !step.done ? (
                  <Button size="small" onClick={() => navigate(step.route)}>
                    Go
                  </Button>
                ) : null
              }
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                {step.done ? (
                  <CheckCircleIcon color="success" fontSize="small" />
                ) : (
                  <RadioButtonUncheckedIcon sx={{ color: 'text.disabled' }} fontSize="small" />
                )}
              </ListItemIcon>
              <ListItemText
                primary={step.label}
                secondary={!step.done ? step.tip : undefined}
                primaryTypographyProps={{
                  variant: 'body2',
                  fontWeight: step.done ? 400 : 600,
                  sx: step.done ? { textDecoration: 'line-through', color: 'text.secondary' } : {},
                }}
                secondaryTypographyProps={{ variant: 'caption' }}
              />
            </ListItem>
          ))}
        </List>
      </CardContent>
    </Card>
  );
}
