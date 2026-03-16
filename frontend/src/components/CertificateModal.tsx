import { useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  CircularProgress,
  Tooltip,
  IconButton,
} from "@mui/material";
import {
  Download as DownloadIcon,
  Close as CloseIcon,
  Verified as VerifiedIcon,
  EmojiEvents as TrophyIcon,
} from "@mui/icons-material";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";

// ─── Types ────────────────────────────────────────────────────────────────────
interface CertificateModalProps {
  open: boolean;
  onClose: () => void;
  recipientName: string;
  projectName?: string;
  suiteId: string;
  validationsPassed: string[];
  overallPassed: boolean;
  issuedAt?: string; // ISO date string; defaults to now
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatDate(iso?: string) {
  const d = iso ? new Date(iso) : new Date();
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function labelForValidator(key: string) {
  const map: Record<string, string> = {
    fairness: "AI Fairness",
    transparency: "Model Transparency",
    privacy: "Data Privacy",
    accountability: "Audit Accountability",
  };
  return map[key] ?? key;
}

// Decorative SVG border pattern as inline component
function DecorativeBorder() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#c9a84c" />
          <stop offset="50%" stopColor="#f0d080" />
          <stop offset="100%" stopColor="#c9a84c" />
        </linearGradient>
        <linearGradient id="cornerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f0d080" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#c9a84c" stopOpacity="0.6" />
        </linearGradient>
      </defs>

      {/* Outer border */}
      <rect
        x="8"
        y="8"
        width="calc(100% - 16px)"
        height="calc(100% - 16px)"
        rx="4"
        fill="none"
        stroke="url(#borderGrad)"
        strokeWidth="2.5"
        vectorEffect="non-scaling-stroke"
      />
      {/* Inner border */}
      <rect
        x="18"
        y="18"
        width="calc(100% - 36px)"
        height="calc(100% - 36px)"
        rx="2"
        fill="none"
        stroke="url(#borderGrad)"
        strokeWidth="1"
        strokeDasharray="6 4"
        vectorEffect="non-scaling-stroke"
      />

      {/* Corner ornaments – top-left */}
      <g fill="url(#cornerGrad)">
        <circle cx="24" cy="24" r="3" />
        <circle cx="36" cy="24" r="1.5" />
        <circle cx="24" cy="36" r="1.5" />
      </g>
      {/* top-right */}
      <g fill="url(#cornerGrad)">
        <circle cx="calc(100% - 24px)" cy="24" r="3" />
        <circle cx="calc(100% - 36px)" cy="24" r="1.5" />
        <circle cx="calc(100% - 24px)" cy="36" r="1.5" />
      </g>
      {/* bottom-left */}
      <g fill="url(#cornerGrad)">
        <circle cx="24" cy="calc(100% - 24px)" r="3" />
        <circle cx="36" cy="calc(100% - 24px)" r="1.5" />
        <circle cx="24" cy="calc(100% - 36px)" r="1.5" />
      </g>
      {/* bottom-right */}
      <g fill="url(#cornerGrad)">
        <circle cx="calc(100% - 24px)" cy="calc(100% - 24px)" r="3" />
        <circle cx="calc(100% - 36px)" cy="calc(100% - 24px)" r="1.5" />
        <circle cx="calc(100% - 24px)" cy="calc(100% - 36px)" r="1.5" />
      </g>
    </svg>
  );
}

// ─── Certificate Canvas (the actual printable certificate) ───────────────────
function CertificateCanvas({
  recipientName,
  projectName,
  suiteId,
  validationsPassed,
  overallPassed,
  issuedAt,
}: Omit<CertificateModalProps, "open" | "onClose">) {
  const passed = validationsPassed.filter(Boolean);
  const date = formatDate(issuedAt);
  const certId = `ETHAI-${suiteId.substring(0, 8).toUpperCase()}`;

  return (
    <Box
      sx={{
        // Fixed A4 landscape-ish ratio for crisp PDF rendering
        width: 860,
        minHeight: 600,
        position: "relative",
        background: "linear-gradient(145deg, #0a0f1e 0%, #0d1a2e 50%, #0a1520 100%)",
        borderRadius: "8px",
        overflow: "hidden",
        fontFamily: "'Inter', sans-serif",
        color: "#f8fafc",
        p: 0,
        flexShrink: 0,
      }}
    >
      {/* Decorative Background Geometry */}
      <Box
        sx={{
          position: "absolute",
          top: -80,
          right: -80,
          width: 320,
          height: 320,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />
      <Box
        sx={{
          position: "absolute",
          bottom: -60,
          left: -60,
          width: 280,
          height: 280,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(201,168,76,0.10) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />
      {/* Subtle grid pattern */}
      <Box
        sx={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(201,168,76,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(201,168,76,0.04) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
          pointerEvents: "none",
        }}
      />

      {/* Gold SVG Border */}
      <DecorativeBorder />

      {/* ─── Content ─────────────────────────────────────────────────────── */}
      <Box sx={{ position: "relative", px: 7, py: 5 }}>
        {/* Header */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            mb: 2,
          }}
        >
          {/* Logo / Org */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Box
              sx={{
                width: 44,
                height: 44,
                borderRadius: "10px",
                background: "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 0 16px rgba(59,130,246,0.4)",
              }}
            >
              <VerifiedIcon sx={{ color: "#fff", fontSize: 24 }} />
            </Box>
            <Box>
              <Typography
                sx={{
                  fontSize: "0.95rem",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  color: "#3b82f6",
                  lineHeight: 1.1,
                  textTransform: "uppercase",
                }}
              >
                Ethical AI Platform
              </Typography>
              <Typography
                sx={{
                  fontSize: "0.68rem",
                  color: "#94a3b8",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
              >
                Responsible AI Certification Authority
              </Typography>
            </Box>
          </Box>

          {/* Trophy / seal */}
          <Box
            sx={{
              width: 64,
              height: 64,
              borderRadius: "50%",
              background: overallPassed
                ? "linear-gradient(135deg, #b8860b 0%, #f0d060 50%, #b8860b 100%)"
                : "linear-gradient(135deg, #4b5563 0%, #6b7280 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: overallPassed
                ? "0 0 24px rgba(201,168,76,0.5), 0 0 48px rgba(201,168,76,0.2)"
                : "none",
              border: "2px solid",
              borderColor: overallPassed ? "#f0d060" : "#4b5563",
            }}
          >
            <TrophyIcon
              sx={{
                fontSize: 32,
                color: overallPassed ? "#0a0f1e" : "#9ca3af",
              }}
            />
          </Box>
        </Box>

        {/* Gold divider */}
        <Box
          sx={{
            width: "100%",
            height: "1px",
            background:
              "linear-gradient(90deg, transparent, #c9a84c 20%, #f0d080 50%, #c9a84c 80%, transparent)",
            mb: 3.5,
          }}
        />

        {/* Certificate Label */}
        <Typography
          sx={{
            fontSize: "0.75rem",
            fontWeight: 600,
            letterSpacing: "0.25em",
            textTransform: "uppercase",
            color: "#c9a84c",
            textAlign: "center",
            mb: 1.5,
          }}
        >
          Certificate of{" "}
          {overallPassed ? "Ethical AI Compliance" : "Validation Assessment"}
        </Typography>

        {/* Main Title */}
        <Typography
          sx={{
            fontSize: "2.4rem",
            fontWeight: 800,
            letterSpacing: "-0.02em",
            textAlign: "center",
            lineHeight: 1.1,
            background: "linear-gradient(135deg, #e2e8f0 0%, #ffffff 50%, #cbd5e1 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            mb: 0.5,
          }}
        >
          {overallPassed ? "AI Ethics Compliance" : "Validation Assessment"}
        </Typography>
        <Typography
          sx={{
            fontSize: "1.1rem",
            fontWeight: 300,
            textAlign: "center",
            color: "#94a3b8",
            letterSpacing: "0.04em",
            mb: 3,
          }}
        >
          {overallPassed
            ? "This document certifies successful validation"
            : "This document records the validation assessment"}
        </Typography>

        {/* This certifies that */}
        <Typography
          sx={{
            textAlign: "center",
            fontSize: "0.8rem",
            color: "#94a3b8",
            fontStyle: "italic",
            mb: 0.75,
          }}
        >
          This is to certify that
        </Typography>

        {/* Recipient Name */}
        <Box sx={{ textAlign: "center", mb: 2.5, position: "relative" }}>
          <Box
            sx={{
              display: "inline-block",
              borderBottom: "2px solid",
              borderColor: "rgba(201,168,76,0.6)",
              pb: 0.5,
              px: 2,
            }}
          >
            <Typography
              sx={{
                fontSize: "2rem",
                fontWeight: 700,
                letterSpacing: "0.02em",
                background:
                  "linear-gradient(135deg, #f0d080 0%, #c9a84c 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
                fontStyle: "italic",
              }}
            >
              {recipientName}
            </Typography>
          </Box>
        </Box>

        {/* Description */}
        <Typography
          sx={{
            textAlign: "center",
            fontSize: "0.875rem",
            color: "#cbd5e1",
            maxWidth: 580,
            mx: "auto",
            lineHeight: 1.7,
            mb: 3,
          }}
        >
          {overallPassed
            ? `has successfully validated the AI system against all selected ethical guidelines,
              demonstrating compliance with responsible AI principles through rigorous automated testing.`
            : `has completed an AI system validation assessment. The results of all selected
              ethical checks are recorded in this official audit document.`}
        </Typography>

        {/* Validation Results Grid */}
        {passed.length > 0 && (
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              flexWrap: "wrap",
              gap: 1.5,
              mb: 3.5,
            }}
          >
            {passed.map((v) => (
              <Box
                key={v}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0.75,
                  px: 2,
                  py: 0.75,
                  border: "1px solid",
                  borderColor: "rgba(201,168,76,0.35)",
                  borderRadius: "20px",
                  background: "rgba(201,168,76,0.07)",
                  backdropFilter: "blur(4px)",
                }}
              >
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: overallPassed ? "#22c55e" : "#f59e0b",
                    boxShadow: overallPassed
                      ? "0 0 6px #22c55e"
                      : "0 0 6px #f59e0b",
                    flexShrink: 0,
                  }}
                />
                <Typography
                  sx={{
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    color: "#e2e8f0",
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                  }}
                >
                  {labelForValidator(v)}
                </Typography>
              </Box>
            ))}
          </Box>
        )}

        {/* Gold divider */}
        <Box
          sx={{
            width: "100%",
            height: "1px",
            background:
              "linear-gradient(90deg, transparent, #c9a84c 20%, #f0d080 50%, #c9a84c 80%, transparent)",
            mb: 3,
          }}
        />

        {/* Footer: Project | Date | Cert ID | Signatures */}
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
          }}
        >
          {/* Left: metadata */}
          <Box>
            {projectName && (
              <Box sx={{ mb: 0.75 }}>
                <Typography
                  sx={{
                    fontSize: "0.65rem",
                    letterSpacing: "0.12em",
                    color: "#64748b",
                    textTransform: "uppercase",
                    mb: 0.2,
                  }}
                >
                  Project
                </Typography>
                <Typography
                  sx={{ fontSize: "0.85rem", fontWeight: 600, color: "#e2e8f0" }}
                >
                  {projectName}
                </Typography>
              </Box>
            )}
            <Box sx={{ mb: 0.75 }}>
              <Typography
                sx={{
                  fontSize: "0.65rem",
                  letterSpacing: "0.12em",
                  color: "#64748b",
                  textTransform: "uppercase",
                  mb: 0.2,
                }}
              >
                Date of Issuance
              </Typography>
              <Typography
                sx={{ fontSize: "0.85rem", fontWeight: 600, color: "#e2e8f0" }}
              >
                {date}
              </Typography>
            </Box>
            <Box>
              <Typography
                sx={{
                  fontSize: "0.65rem",
                  letterSpacing: "0.12em",
                  color: "#64748b",
                  textTransform: "uppercase",
                  mb: 0.2,
                }}
              >
                Certificate ID
              </Typography>
              <Typography
                sx={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "#3b82f6",
                  fontFamily: "monospace",
                  letterSpacing: "0.08em",
                }}
              >
                {certId}
              </Typography>
            </Box>
          </Box>

          {/* Center: Status Badge */}
          <Box sx={{ textAlign: "center" }}>
            <Box
              sx={{
                display: "inline-flex",
                flexDirection: "column",
                alignItems: "center",
                px: 3,
                py: 1.5,
                border: "2px solid",
                borderColor: overallPassed
                  ? "rgba(34,197,94,0.5)"
                  : "rgba(239,68,68,0.5)",
                borderRadius: "8px",
                background: overallPassed
                  ? "rgba(34,197,94,0.08)"
                  : "rgba(239,68,68,0.08)",
              }}
            >
              <Typography
                sx={{
                  fontSize: "0.65rem",
                  letterSpacing: "0.16em",
                  color: "#64748b",
                  textTransform: "uppercase",
                  mb: 0.25,
                }}
              >
                Verification Status
              </Typography>
              <Typography
                sx={{
                  fontSize: "1.1rem",
                  fontWeight: 800,
                  letterSpacing: "0.1em",
                  color: overallPassed ? "#22c55e" : "#ef4444",
                  textTransform: "uppercase",
                }}
              >
                {overallPassed ? "✓ Certified" : "✗ Not Certified"}
              </Typography>
            </Box>
          </Box>

          {/* Right: Signature area */}
          <Box sx={{ textAlign: "right" }}>
            <Box
              sx={{
                borderBottom: "1px solid rgba(148,163,184,0.3)",
                mb: 0.5,
                pb: 1,
                minWidth: 140,
              }}
            >
              {/* Stylised "signature" */}
              <Typography
                sx={{
                  fontFamily: "'Georgia', serif",
                  fontSize: "1.4rem",
                  fontStyle: "italic",
                  color: "#c9a84c",
                  lineHeight: 1,
                  letterSpacing: "0.02em",
                }}
              >
                Ethical AI Platform
              </Typography>
            </Box>
            <Typography
              sx={{
                fontSize: "0.65rem",
                letterSpacing: "0.12em",
                color: "#64748b",
                textTransform: "uppercase",
              }}
            >
              Authorised Signatory
            </Typography>
            <Typography
              sx={{
                fontSize: "0.7rem",
                color: "#94a3b8",
                mt: 0.25,
              }}
            >
              Responsible AI Division
            </Typography>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}

// ─── Main Modal ───────────────────────────────────────────────────────────────
export default function CertificateModal({
  open,
  onClose,
  recipientName,
  projectName,
  suiteId,
  validationsPassed,
  overallPassed,
  issuedAt,
}: CertificateModalProps) {
  const certRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);

  const handleDownloadPdf = async () => {
    if (!certRef.current) return;
    setExporting(true);
    try {
      const canvas = await html2canvas(certRef.current, {
        scale: 2,
        useCORS: true,
        backgroundColor: null,
        logging: false,
      });

      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF({
        orientation: "landscape",
        unit: "px",
        format: [canvas.width / 2, canvas.height / 2],
      });

      pdf.addImage(imgData, "PNG", 0, 0, canvas.width / 2, canvas.height / 2);
      pdf.save(`ethical_ai_certificate_${suiteId.substring(0, 8)}.pdf`);
    } catch (err) {
      console.error("PDF export failed", err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={false}
      PaperProps={{
        sx: {
          background: "#060c18",
          border: "1px solid rgba(201,168,76,0.2)",
          borderRadius: "16px",
          boxShadow: "0 24px 80px rgba(0,0,0,0.8), 0 0 60px rgba(201,168,76,0.08)",
          maxWidth: "960px",
          width: "100%",
          overflow: "hidden",
        },
      }}
    >
      {/* Dialog Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 3,
          py: 2,
          borderBottom: "1px solid rgba(201,168,76,0.15)",
          background: "rgba(201,168,76,0.03)",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <TrophyIcon sx={{ color: "#c9a84c", fontSize: 22 }} />
          <Typography sx={{ fontWeight: 700, fontSize: "1rem", color: "#f8fafc" }}>
            Certificate Preview
          </Typography>
          {overallPassed && (
            <Box
              sx={{
                px: 1.5,
                py: 0.3,
                borderRadius: "12px",
                background: "rgba(34,197,94,0.12)",
                border: "1px solid rgba(34,197,94,0.3)",
              }}
            >
              <Typography sx={{ fontSize: "0.7rem", fontWeight: 700, color: "#22c55e", letterSpacing: "0.06em" }}>
                PASSED
              </Typography>
            </Box>
          )}
        </Box>
        <Tooltip title="Close">
          <IconButton onClick={onClose} size="small" sx={{ color: "#64748b" }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Certificate Preview */}
      <DialogContent
        sx={{
          p: 3,
          display: "flex",
          justifyContent: "center",
          background: "rgba(0,0,0,0.2)",
          overflowX: "auto",
        }}
      >
        <Box
          ref={certRef}
          sx={{
            display: "inline-block",
            boxShadow: "0 8px 48px rgba(0,0,0,0.6), 0 0 24px rgba(201,168,76,0.12)",
            borderRadius: "8px",
          }}
        >
          <CertificateCanvas
            recipientName={recipientName}
            projectName={projectName}
            suiteId={suiteId}
            validationsPassed={validationsPassed}
            overallPassed={overallPassed}
            issuedAt={issuedAt}
          />
        </Box>
      </DialogContent>

      {/* Actions */}
      <DialogActions
        sx={{
          px: 3,
          py: 2,
          gap: 1.5,
          borderTop: "1px solid rgba(201,168,76,0.12)",
          justifyContent: "flex-end",
        }}
      >
        <Button variant="outlined" onClick={onClose} sx={{ borderColor: "rgba(148,163,184,0.3)", color: "#94a3b8" }}>
          Close
        </Button>
        <Button
          variant="contained"
          startIcon={exporting ? <CircularProgress size={16} color="inherit" /> : <DownloadIcon />}
          onClick={handleDownloadPdf}
          disabled={exporting}
          sx={{
            background: overallPassed
              ? "linear-gradient(135deg, #b8860b 0%, #d4a017 50%, #b8860b 100%)"
              : "linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%)",
            color: overallPassed ? "#0a0f1e" : "#fff",
            fontWeight: 700,
            letterSpacing: "0.04em",
            "&:hover": {
              background: overallPassed
                ? "linear-gradient(135deg, #d4a017 0%, #f0c030 50%, #d4a017 100%)"
                : "linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)",
            },
          }}
        >
          {exporting ? "Generating PDF…" : "Download PDF"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
