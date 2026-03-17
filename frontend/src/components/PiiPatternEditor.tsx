import {
  Add as AddIcon,
  DeleteOutline as DeleteIcon,
} from "@mui/icons-material";
import {
  Box,
  Button,
  IconButton,
  TextField,
  Typography,
} from "@mui/material";

export interface PiiPatternRow {
  id: string;
  name: string;
  pattern: string;
  testValue: string;
}

interface PiiPatternEditorProps {
  rows: PiiPatternRow[];
  disabled?: boolean;
  onChange: (rows: PiiPatternRow[]) => void;
}

const makeRow = (): PiiPatternRow => ({
  id: Math.random().toString(36).slice(2),
  name: "",
  pattern: "",
  testValue: "",
});

export default function PiiPatternEditor({
  rows,
  disabled = false,
  onChange,
}: PiiPatternEditorProps) {
  const updateRow = (id: string, patch: Partial<PiiPatternRow>) => {
    onChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  };

  const addRow = () => onChange([...rows, makeRow()]);

  const removeRow = (id: string) => onChange(rows.filter((row) => row.id !== id));

  const testResult = (pattern: string, value: string): string => {
    if (!pattern || !value) return "";
    try {
      const regex = new RegExp(pattern);
      return regex.test(value) ? "Matches" : "No match";
    } catch {
      return "Invalid regex";
    }
  };

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
        Custom PII Patterns
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Add regex patterns to detect domain-specific identifiers.
      </Typography>

      {rows.map((row) => (
        <Box
          key={row.id}
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "1fr 1.3fr 1.3fr auto" },
            gap: 1,
            mb: 1,
            alignItems: "start",
          }}
        >
          <TextField
            label="Pattern Name"
            size="small"
            value={row.name}
            onChange={(e) => updateRow(row.id, { name: e.target.value })}
            disabled={disabled}
            placeholder="employee_id"
          />
          <TextField
            label="Regex"
            size="small"
            value={row.pattern}
            onChange={(e) => updateRow(row.id, { pattern: e.target.value })}
            disabled={disabled}
            placeholder="\\bEMP-\\d{6}\\b"
            helperText={row.pattern ? testResult(row.pattern, row.testValue) : ""}
          />
          <TextField
            label="Test Value"
            size="small"
            value={row.testValue}
            onChange={(e) => updateRow(row.id, { testValue: e.target.value })}
            disabled={disabled}
            placeholder="EMP-123456"
          />
          <IconButton
            aria-label="Delete pattern row"
            onClick={() => removeRow(row.id)}
            disabled={disabled}
            sx={{ mt: 0.5 }}
          >
            <DeleteIcon />
          </IconButton>
        </Box>
      ))}

      <Button
        variant="outlined"
        size="small"
        startIcon={<AddIcon />}
        onClick={addRow}
        disabled={disabled}
      >
        Add Pattern
      </Button>
    </Box>
  );
}
