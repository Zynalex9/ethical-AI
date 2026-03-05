"""
HIPAA Safe Harbor De-Identification Checker for EthicScan AI.

Checks for the presence of the 18 HIPAA Safe Harbor identifier categories
in a dataset's columns and values. Each identifier type is a named
sub-check with individual PASS/FAIL status.
"""

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

# ============================================================================
# The 18 HIPAA Safe Harbor identifier categories
# ============================================================================

HIPAA_IDENTIFIERS = [
    {
        "id": "names",
        "label": "Names",
        "description": "Full names, first names, last names, initials",
        "column_patterns": [r"\bname\b", r"\bfirst.?name\b", r"\blast.?name\b", r"\bfull.?name\b", r"\bsurname\b", r"\binitial\b"],
        "value_patterns": [],
    },
    {
        "id": "dates",
        "label": "Dates (except year)",
        "description": "Dates directly related to an individual (birth, admission, discharge, death) other than year",
        "column_patterns": [r"\bdate\b", r"\bbirth\b", r"\bdob\b", r"\badmission\b", r"\bdischarge\b", r"\bdeath\b", r"\bdate.?of.?birth\b"],
        "value_patterns": [r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}", r"\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}"],
    },
    {
        "id": "geographic",
        "label": "Geographic data smaller than state",
        "description": "Street address, city, ZIP code, county, precinct, geocodes",
        "column_patterns": [r"\baddress\b", r"\bstreet\b", r"\bcity\b", r"\bzip\b", r"\bpostal\b", r"\bcounty\b", r"\bgeocode\b", r"\blatitude\b", r"\blongitude\b", r"\blat\b", r"\blon\b", r"\blng\b"],
        "value_patterns": [r"\b\d{5}(-\d{4})?\b"],  # ZIP code pattern
    },
    {
        "id": "phone",
        "label": "Phone numbers",
        "description": "Telephone numbers",
        "column_patterns": [r"\bphone\b", r"\btelephone\b", r"\bmobile\b", r"\bcell\b", r"\btel\b"],
        "value_patterns": [r"\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}"],
    },
    {
        "id": "fax",
        "label": "Fax numbers",
        "description": "Fax numbers",
        "column_patterns": [r"\bfax\b"],
        "value_patterns": [],
    },
    {
        "id": "email",
        "label": "Email addresses",
        "description": "Electronic mail addresses",
        "column_patterns": [r"\bemail\b", r"\be.?mail\b"],
        "value_patterns": [r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"],
    },
    {
        "id": "ssn",
        "label": "Social Security numbers",
        "description": "Social Security numbers",
        "column_patterns": [r"\bssn\b", r"\bsocial.?security\b", r"\bss.?number\b"],
        "value_patterns": [r"\b\d{3}[\-\s]?\d{2}[\-\s]?\d{4}\b"],
    },
    {
        "id": "medical_record",
        "label": "Medical record numbers",
        "description": "Medical record numbers",
        "column_patterns": [r"\bmedical.?record\b", r"\bmrn\b", r"\bpatient.?id\b", r"\bmed.?rec\b"],
        "value_patterns": [],
    },
    {
        "id": "health_plan",
        "label": "Health plan beneficiary numbers",
        "description": "Health plan beneficiary numbers",
        "column_patterns": [r"\bhealth.?plan\b", r"\binsurance.?id\b", r"\bpolicy.?number\b", r"\bmember.?id\b", r"\bbeneficiary\b"],
        "value_patterns": [],
    },
    {
        "id": "account",
        "label": "Account numbers",
        "description": "Account numbers",
        "column_patterns": [r"\baccount\b", r"\bacct\b", r"\bbank.?account\b"],
        "value_patterns": [],
    },
    {
        "id": "certificate_license",
        "label": "Certificate/license numbers",
        "description": "Certificate/license numbers",
        "column_patterns": [r"\bcertificate\b", r"\blicense\b", r"\blicence\b", r"\bpermit\b"],
        "value_patterns": [],
    },
    {
        "id": "vehicle",
        "label": "Vehicle identifiers (VIN)",
        "description": "Vehicle identifiers and serial numbers including license plate numbers",
        "column_patterns": [r"\bvin\b", r"\bvehicle\b", r"\blicense.?plate\b", r"\bplate.?number\b"],
        "value_patterns": [r"\b[A-HJ-NPR-Z0-9]{17}\b"],  # VIN pattern
    },
    {
        "id": "device",
        "label": "Device identifiers and serial numbers",
        "description": "Device identifiers and serial numbers",
        "column_patterns": [r"\bdevice.?id\b", r"\bserial\b", r"\bimei\b", r"\bmac.?address\b", r"\bhardware.?id\b"],
        "value_patterns": [r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}"],  # MAC address
    },
    {
        "id": "url",
        "label": "Web URLs",
        "description": "Web Universal Resource Locators (URLs)",
        "column_patterns": [r"\burl\b", r"\bwebsite\b", r"\bweb.?address\b", r"\bhomepage\b"],
        "value_patterns": [r"https?://[^\s]+"],
    },
    {
        "id": "ip_address",
        "label": "IP addresses",
        "description": "Internet Protocol (IP) address numbers",
        "column_patterns": [r"\bip\b", r"\bip.?address\b", r"\bipv[46]\b"],
        "value_patterns": [r"\b(?:\d{1,3}\.){3}\d{1,3}\b"],
    },
    {
        "id": "biometric",
        "label": "Biometric identifiers",
        "description": "Biometric identifiers, including finger and voice prints",
        "column_patterns": [r"\bbiometric\b", r"\bfingerprint\b", r"\bvoice.?print\b", r"\bretina\b", r"\biris\b", r"\bfacial\b"],
        "value_patterns": [],
    },
    {
        "id": "photo",
        "label": "Full face photographs",
        "description": "Full face photographic images and any comparable images",
        "column_patterns": [r"\bphoto\b", r"\bimage\b", r"\bpicture\b", r"\bportrait\b", r"\bheadshot\b", r"\bface\b"],
        "value_patterns": [],
    },
    {
        "id": "unique_id",
        "label": "Any other unique identifying number",
        "description": "Any other unique identifying number, characteristic, or code",
        "column_patterns": [r"\bnational.?id\b", r"\bpassport\b", r"\btax.?id\b", r"\bein\b", r"\bdriver.?license\b"],
        "value_patterns": [],
    },
]


@dataclass
class HIPAACheckResult:
    """Result for a single HIPAA identifier category."""
    identifier_id: str
    label: str
    description: str
    passed: bool  # True = NOT detected (safe), False = detected (risky)
    flagged_columns: List[str] = field(default_factory=list)
    flagged_value_samples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HIPAAReport:
    """Overall HIPAA Safe Harbor check report."""
    overall_passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    results: List[HIPAACheckResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


class HIPAAChecker:
    """
    Checks a dataset against the 18 HIPAA Safe Harbor identifier categories.

    Each category is checked by:
    1. Column name matching (regex patterns on column names).
    2. Value scanning (regex patterns on sampled cell values).

    A category is PASS if *no* columns or values match. FAIL otherwise.
    """

    SAMPLE_SIZE = 200  # max rows to scan per column for value patterns

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def check(self) -> HIPAAReport:
        """Run all 18 HIPAA Safe Harbor checks.

        Returns
        -------
        HIPAAReport
        """
        results: List[HIPAACheckResult] = []

        for identifier in HIPAA_IDENTIFIERS:
            result = self._check_identifier(identifier)
            results.append(result)

        passed_checks = sum(1 for r in results if r.passed)
        failed_checks = len(results) - passed_checks
        overall_passed = failed_checks == 0

        report = HIPAAReport(
            overall_passed=overall_passed,
            total_checks=len(results),
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            results=results,
        )

        logger.info(
            "HIPAA check: %d/%d passed, overall=%s",
            passed_checks,
            len(results),
            "PASS" if overall_passed else "FAIL",
        )
        return report

    def _check_identifier(self, identifier: Dict[str, Any]) -> HIPAACheckResult:
        """Check a single HIPAA identifier category."""
        flagged_columns: List[str] = []
        flagged_value_samples: List[str] = []

        # 1. Column name matching
        col_patterns = [re.compile(p, re.IGNORECASE) for p in identifier["column_patterns"]]
        for col in self.df.columns:
            col_lower = col.lower().strip()
            for pat in col_patterns:
                if pat.search(col_lower):
                    flagged_columns.append(col)
                    break

        # 2. Value scanning
        val_patterns = [re.compile(p) for p in identifier.get("value_patterns", [])]
        if val_patterns:
            for col in self.df.columns:
                if self.df[col].dtype != object:
                    continue
                sample = self.df[col].dropna().head(self.SAMPLE_SIZE)
                for val in sample:
                    val_str = str(val)
                    for pat in val_patterns:
                        if pat.search(val_str):
                            # Record only unique flagged column+sample
                            sample_text = f"{col}: {val_str[:60]}"
                            if sample_text not in flagged_value_samples:
                                flagged_value_samples.append(sample_text)
                            if col not in flagged_columns:
                                flagged_columns.append(col)
                            break  # one match per value is enough
                    if len(flagged_value_samples) >= 5:
                        break

        passed = len(flagged_columns) == 0 and len(flagged_value_samples) == 0

        return HIPAACheckResult(
            identifier_id=identifier["id"],
            label=identifier["label"],
            description=identifier["description"],
            passed=passed,
            flagged_columns=flagged_columns,
            flagged_value_samples=flagged_value_samples[:5],
        )
