// HelpTooltip — "?" icon that shows a plain-English explanation on hover
// Usage: <HelpTooltip term="Demographic Parity" />

import { Tooltip, IconButton, Typography, Box } from '@mui/material';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';

/**
 * Dictionary of ethical AI terms and their plain-English explanations.
 * Used by the HelpTooltip component for in-app contextual help.
 */
const GLOSSARY: Record<string, string> = {
  'Demographic Parity':
    'Requires that each demographic group receives a positive outcome at roughly the same rate. Also known as "statistical parity".',
  'Equal Opportunity':
    'Requires that the model has the same true positive rate (sensitivity) across all groups. Focuses on people who actually deserve a positive outcome.',
  'Equalized Odds':
    'Requires that both the true positive rate AND false positive rate are equal across groups. Stricter than equal opportunity.',
  'Disparate Impact':
    'Ratio of favourable outcome rates between groups. A value below 0.80 (the "80% rule") indicates adverse impact.',
  'SHAP':
    'SHapley Additive exPlanations — assigns each feature a value representing how much it contributed to a specific prediction. Based on game theory.',
  'LIME':
    'Local Interpretable Model-agnostic Explanations — builds a simple model around a single prediction to explain which features mattered most.',
  'PII':
    'Personally Identifiable Information — data that can identify an individual (name, email, SSN, phone number, address).',
  'k-Anonymity':
    'A privacy property where every record is indistinguishable from at least k−1 other records on quasi-identifier attributes. Higher k = stronger privacy.',
  'l-Diversity':
    'Extends k-anonymity by requiring at least l distinct values for the sensitive attribute within each equivalence class. Prevents attribute disclosure.',
  'Quasi-Identifiers':
    'Attributes that are not unique identifiers on their own but can be combined to re-identify individuals (e.g., age + zip code + gender).',
  'Sensitive Attribute':
    'A protected characteristic (gender, race, age, disability) that should not influence model decisions unfairly.',
  'Fairness Threshold':
    'The minimum acceptable value for a fairness metric. For example, demographic parity ratio ≥ 0.80 means at least 80% parity.',
  'Model Card':
    'A documentation sheet describing a model\'s purpose, performance, limitations, and ethical considerations.',
  'Traceability Matrix':
    'A table linking ethical requirements → datasets → models → validation results, showing which requirements have been tested and their outcomes.',
  'Root-Cause Analysis':
    'When a validation fails, this traces back to identify which specific data feature, model behavior, or threshold caused the failure.',
  'Accountability':
    'Complete audit trail of who did what, when, and why — including model uploads, validation runs, and configuration changes.',
  'Confusion Matrix':
    'A table showing True Positives, False Positives, True Negatives, and False Negatives for a classification model.',
  'Feature Importance':
    'A ranking of which input features (columns) the model relies on most for making predictions.',
};

interface HelpTooltipProps {
  /** The term to look up in the glossary */
  term: string;
  /** Override the glossary with a custom explanation */
  explanation?: string;
  /** Size of the icon (default: 'small') */
  size?: 'small' | 'medium';
}

export default function HelpTooltip({
  term,
  explanation,
  size = 'small',
}: HelpTooltipProps) {
  const text = explanation || GLOSSARY[term] || `No definition available for "${term}".`;

  return (
    <Tooltip
      title={
        <Box sx={{ maxWidth: 300 }}>
          <Typography variant="subtitle2" fontWeight={700} gutterBottom>
            {term}
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.5 }}>
            {text}
          </Typography>
        </Box>
      }
      arrow
      placement="top"
      enterDelay={200}
    >
      <IconButton
        size={size}
        sx={{
          ml: 0.5,
          p: 0.25,
          color: 'text.secondary',
          '&:hover': { color: 'primary.main' },
        }}
        tabIndex={-1}
      >
        <HelpOutlineIcon fontSize={size} />
      </IconButton>
    </Tooltip>
  );
}

/** Export the glossary for use in other components */
export { GLOSSARY };
