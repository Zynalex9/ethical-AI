import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import type { DatasetProfileResponse } from "../services/api";

interface DatasetProfileProps {
  profile: DatasetProfileResponse;
  selectedQuasiIdentifiers: string[];
  selectedSensitiveAttribute: string;
  onToggleQuasiIdentifier: (column: string) => void;
  onSetSensitiveAttribute: (column: string) => void;
}

const fmt = (value: number | null | undefined): string => {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toFixed(4);
};

const likelySensitive = (dtype: string, uniqueCount: number, rowsProfiled: number): boolean => {
  const lower = dtype.toLowerCase();
  const isTextLike = lower.includes("object") || lower.includes("string") || lower.includes("category");
  if (!isTextLike || rowsProfiled <= 0) return false;
  return uniqueCount / rowsProfiled >= 0.7;
};

export default function DatasetProfile({
  profile,
  selectedQuasiIdentifiers,
  selectedSensitiveAttribute,
  onToggleQuasiIdentifier,
  onSetSensitiveAttribute,
}: DatasetProfileProps) {
  return (
    <Card sx={{ mt: 2 }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 0.5 }}>
          Dataset Profile: {profile.name}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Profiled {profile.rows_profiled.toLocaleString()} rows out of {profile.row_count.toLocaleString()}.
        </Typography>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Column</TableCell>
                <TableCell>Type</TableCell>
                <TableCell align="right">Unique</TableCell>
                <TableCell align="right">Null %</TableCell>
                <TableCell>Stats / Top Values</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {profile.columns.map((col) => {
                const isSensitiveCandidate = likelySensitive(
                  col.dtype,
                  col.unique_count,
                  profile.rows_profiled,
                );
                const isQI = selectedQuasiIdentifiers.includes(col.column);
                const isSensitive = selectedSensitiveAttribute === col.column;

                return (
                  <TableRow key={col.column} hover>
                    <TableCell>
                      <Stack direction="row" spacing={1} alignItems="center" useFlexGap flexWrap="wrap">
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {col.column}
                        </Typography>
                        {isSensitiveCandidate && (
                          <Chip label="Potentially Sensitive" color="warning" size="small" />
                        )}
                        {isQI && <Chip label="Quasi-ID" color="info" size="small" />}
                        {isSensitive && <Chip label="Sensitive" color="error" size="small" />}
                      </Stack>
                    </TableCell>
                    <TableCell>{col.dtype}</TableCell>
                    <TableCell align="right">{col.unique_count.toLocaleString()}</TableCell>
                    <TableCell align="right">{col.null_percentage.toFixed(2)}%</TableCell>
                    <TableCell>
                      {col.numeric_stats ? (
                        <Typography variant="caption" color="text.secondary">
                          min {fmt(col.numeric_stats.min)} | max {fmt(col.numeric_stats.max)} | mean {fmt(col.numeric_stats.mean)} | median {fmt(col.numeric_stats.median)} | std {fmt(col.numeric_stats.std)}
                        </Typography>
                      ) : (
                        <Stack direction="row" spacing={0.5} useFlexGap flexWrap="wrap">
                          {(col.categorical_top_values || []).slice(0, 10).map((entry) => (
                            <Chip
                              key={`${col.column}-${entry.value}`}
                              size="small"
                              variant="outlined"
                              label={`${entry.value}: ${entry.count}`}
                            />
                          ))}
                        </Stack>
                      )}
                    </TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Button
                          size="small"
                          variant={isQI ? "contained" : "outlined"}
                          onClick={() => onToggleQuasiIdentifier(col.column)}
                        >
                          {isQI ? "Unmark QI" : "Mark QI"}
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          variant={isSensitive ? "contained" : "outlined"}
                          onClick={() => onSetSensitiveAttribute(isSensitive ? "" : col.column)}
                        >
                          {isSensitive ? "Unset Sensitive" : "Mark Sensitive"}
                        </Button>
                      </Stack>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>

        <Box sx={{ mt: 2, display: "flex", gap: 1, flexWrap: "wrap" }}>
          <Chip
            color="info"
            variant="outlined"
            label={`Quasi-identifiers: ${selectedQuasiIdentifiers.length || 0}`}
          />
          <Chip
            color="error"
            variant="outlined"
            label={`Sensitive attribute: ${selectedSensitiveAttribute || "Not selected"}`}
          />
        </Box>
      </CardContent>
    </Card>
  );
}
