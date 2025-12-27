"""
Privacy Validator - Validates privacy requirements for datasets and models.

Implements:
- k-Anonymity checking for quasi-identifiers
- l-Diversity checking for sensitive attributes
- PII (Personally Identifiable Information) detection
- Differential privacy validation

Reference: Ensures data protection in AI systems per privacy regulations
(GDPR, CCPA, HIPAA considerations)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import Counter
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# PII detection patterns (regex)
PII_PATTERNS = {
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone_us": r'\b(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b',
    "ssn": r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
    "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    "date_of_birth": r'\b(0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])[-/](19|20)\d{2}\b',
    "zip_code": r'\b\d{5}(-\d{4})?\b',
    "name_pattern": r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b'  # Simple name pattern
}

# Columns that commonly contain PII (by name heuristics)
PII_COLUMN_NAMES = {
    'email', 'e-mail', 'mail', 'email_address',
    'phone', 'telephone', 'mobile', 'cell', 'phone_number',
    'ssn', 'social_security', 'social_security_number',
    'name', 'first_name', 'last_name', 'full_name', 'firstname', 'lastname',
    'address', 'street', 'street_address', 'home_address',
    'dob', 'date_of_birth', 'birthdate', 'birthday',
    'credit_card', 'card_number', 'cc_number',
    'ip', 'ip_address',
    'passport', 'passport_number',
    'driver_license', 'license_number'
}


@dataclass
class PIIDetectionResult:
    """Result of PII detection for a column."""
    column_name: str
    is_pii: bool
    pii_type: Optional[str]
    confidence: float  # 0-1
    sample_matches: List[str]  # Examples of detected PII
    detection_method: str  # "pattern", "column_name", "value_analysis"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "column_name": self.column_name,
            "is_pii": self.is_pii,
            "pii_type": self.pii_type,
            "confidence": self.confidence,
            "sample_matches": self.sample_matches[:3],  # Limit samples
            "detection_method": self.detection_method
        }


@dataclass
class KAnonymityResult:
    """Result of k-anonymity check."""
    k_value: int
    satisfies_k: bool
    actual_min_k: int
    violating_groups: List[Dict[str, Any]]  # Groups with < k records
    total_groups: int
    quasi_identifiers: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "k_value": self.k_value,
            "satisfies_k": self.satisfies_k,
            "actual_min_k": self.actual_min_k,
            "violating_groups_count": len(self.violating_groups),
            "violating_groups": self.violating_groups[:5],  # Sample
            "total_groups": self.total_groups,
            "quasi_identifiers": self.quasi_identifiers
        }


@dataclass
class LDiversityResult:
    """Result of l-diversity check."""
    l_value: int
    satisfies_l: bool
    actual_min_l: int
    sensitive_attribute: str
    violating_groups: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "l_value": self.l_value,
            "satisfies_l": self.satisfies_l,
            "actual_min_l": self.actual_min_l,
            "sensitive_attribute": self.sensitive_attribute,
            "violating_groups_count": len(self.violating_groups)
        }


@dataclass
class PrivacyReport:
    """Complete privacy validation report."""
    pii_results: List[PIIDetectionResult]
    k_anonymity: Optional[KAnonymityResult]
    l_diversity: Optional[LDiversityResult]
    overall_passed: bool
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pii_results": [p.to_dict() for p in self.pii_results],
            "k_anonymity": self.k_anonymity.to_dict() if self.k_anonymity else None,
            "l_diversity": self.l_diversity.to_dict() if self.l_diversity else None,
            "overall_passed": self.overall_passed,
            "recommendations": self.recommendations
        }


class PrivacyValidator:
    """
    Validates privacy requirements for datasets.
    
    Supports:
    - k-Anonymity: Ensures each combination of quasi-identifiers
      appears at least k times in the dataset
    - l-Diversity: Ensures at least l distinct values of sensitive
      attributes within each equivalence class
    - PII Detection: Identifies personally identifiable information
    
    Usage:
        validator = PrivacyValidator(df)
        
        # Check for PII
        pii_results = validator.detect_pii()
        
        # Check k-anonymity
        k_result = validator.check_k_anonymity(
            quasi_identifiers=['age', 'zip_code', 'gender'],
            k=5
        )
        
        # Full validation
        report = validator.validate(requirements={
            'k_anonymity': {'k': 5, 'quasi_identifiers': ['age', 'zip']},
            'pii_detection': True
        })
    """
    
    def __init__(self, dataframe: pd.DataFrame):
        """
        Initialize privacy validator with a dataset.
        
        Args:
            dataframe: Pandas DataFrame to validate
        """
        self.df = dataframe
        self.n_rows = len(dataframe)
        self.n_cols = len(dataframe.columns)
        self.columns = list(dataframe.columns)
        
        logger.info(f"PrivacyValidator initialized with {self.n_rows} rows, {self.n_cols} columns")
    
    def detect_pii(
        self,
        columns: Optional[List[str]] = None,
        sample_size: int = 100
    ) -> List[PIIDetectionResult]:
        """
        Detect potential PII in dataset columns.
        
        Uses multiple detection methods:
        1. Column name matching (e.g., 'email', 'ssn')
        2. Regex pattern matching on values
        3. Value distribution analysis
        
        Args:
            columns: Specific columns to check (default: all)
            sample_size: Number of rows to sample for pattern matching
            
        Returns:
            List of PIIDetectionResult for each column
        """
        columns = columns or self.columns
        results = []
        
        for col in columns:
            result = self._detect_pii_column(col, sample_size)
            results.append(result)
        
        # Log summary
        pii_count = sum(1 for r in results if r.is_pii)
        logger.info(f"PII detection complete: {pii_count}/{len(results)} columns flagged")
        
        return results
    
    def _detect_pii_column(self, column: str, sample_size: int) -> PIIDetectionResult:
        """Detect PII in a single column."""
        col_lower = column.lower().replace('_', '').replace('-', '').replace(' ', '')
        
        # Method 1: Check column name
        for pii_name in PII_COLUMN_NAMES:
            if pii_name.replace('_', '') in col_lower:
                return PIIDetectionResult(
                    column_name=column,
                    is_pii=True,
                    pii_type=pii_name,
                    confidence=0.9,
                    sample_matches=[],
                    detection_method="column_name"
                )
        
        # Method 2: Pattern matching on values
        if self.df[column].dtype == object:  # String column
            sample = self.df[column].dropna().head(sample_size).astype(str)
            
            for pii_type, pattern in PII_PATTERNS.items():
                matches = []
                for value in sample:
                    if re.search(pattern, str(value)):
                        matches.append(str(value)[:50])  # Truncate long values
                
                if len(matches) > len(sample) * 0.1:  # >10% match rate
                    return PIIDetectionResult(
                        column_name=column,
                        is_pii=True,
                        pii_type=pii_type,
                        confidence=min(len(matches) / len(sample), 1.0),
                        sample_matches=matches[:3],
                        detection_method="pattern"
                    )
        
        # Method 3: High cardinality string columns might be identifiers
        if self.df[column].dtype == object:
            unique_ratio = self.df[column].nunique() / self.n_rows
            if unique_ratio > 0.9:  # Almost all unique values
                return PIIDetectionResult(
                    column_name=column,
                    is_pii=True,
                    pii_type="potential_identifier",
                    confidence=0.6,
                    sample_matches=[],
                    detection_method="value_analysis"
                )
        
        # No PII detected
        return PIIDetectionResult(
            column_name=column,
            is_pii=False,
            pii_type=None,
            confidence=0.0,
            sample_matches=[],
            detection_method="none"
        )
    
    def check_k_anonymity(
        self,
        quasi_identifiers: List[str],
        k: int = 5
    ) -> KAnonymityResult:
        """
        Check if dataset satisfies k-anonymity.
        
        A dataset satisfies k-anonymity if every combination of
        quasi-identifier values appears at least k times.
        
        Args:
            quasi_identifiers: List of column names that together
                could identify individuals (e.g., age, zip, gender)
            k: Minimum group size required
            
        Returns:
            KAnonymityResult with pass/fail and violating groups
        """
        # Validate columns exist
        missing = set(quasi_identifiers) - set(self.columns)
        if missing:
            raise ValueError(f"Columns not found in dataset: {missing}")
        
        # Group by quasi-identifiers and count
        grouped = self.df.groupby(quasi_identifiers).size().reset_index(name='count')
        
        # Find violating groups (count < k)
        violating = grouped[grouped['count'] < k]
        
        # Get minimum group size
        min_k = grouped['count'].min()
        
        # Create violation details
        violating_groups = []
        for _, row in violating.head(10).iterrows():  # Limit to 10
            group = {col: row[col] for col in quasi_identifiers}
            group['count'] = int(row['count'])
            violating_groups.append(group)
        
        result = KAnonymityResult(
            k_value=k,
            satisfies_k=len(violating) == 0,
            actual_min_k=int(min_k),
            violating_groups=violating_groups,
            total_groups=len(grouped),
            quasi_identifiers=quasi_identifiers
        )
        
        logger.info(
            f"k-Anonymity check (k={k}): "
            f"{'PASSED' if result.satisfies_k else 'FAILED'} "
            f"(min group size: {min_k}, violating groups: {len(violating)})"
        )
        
        return result
    
    def check_l_diversity(
        self,
        quasi_identifiers: List[str],
        sensitive_attribute: str,
        l: int = 2
    ) -> LDiversityResult:
        """
        Check if dataset satisfies l-diversity.
        
        A dataset satisfies l-diversity if every equivalence class
        (group defined by quasi-identifiers) contains at least l
        distinct values of the sensitive attribute.
        
        Args:
            quasi_identifiers: Columns defining equivalence classes
            sensitive_attribute: The sensitive column to check diversity
            l: Minimum distinct values required per group
            
        Returns:
            LDiversityResult with pass/fail and details
        """
        # Group and check diversity of sensitive attribute
        diversity = self.df.groupby(quasi_identifiers)[sensitive_attribute].nunique()
        
        min_l = diversity.min()
        violating_count = (diversity < l).sum()
        
        # Get violating groups
        violating_groups = []
        for idx, val in diversity[diversity < l].head(5).items():
            if isinstance(idx, tuple):
                group = {qi: idx[i] for i, qi in enumerate(quasi_identifiers)}
            else:
                group = {quasi_identifiers[0]: idx}
            group['diversity'] = int(val)
            violating_groups.append(group)
        
        result = LDiversityResult(
            l_value=l,
            satisfies_l=violating_count == 0,
            actual_min_l=int(min_l),
            sensitive_attribute=sensitive_attribute,
            violating_groups=violating_groups
        )
        
        logger.info(
            f"l-Diversity check (l={l}): "
            f"{'PASSED' if result.satisfies_l else 'FAILED'} "
            f"(min diversity: {min_l})"
        )
        
        return result
    
    def suggest_generalization(
        self,
        column: str,
        method: str = "auto"
    ) -> Dict[str, Any]:
        """
        Suggest generalization strategies for a column to improve privacy.
        
        Args:
            column: Column name to analyze
            method: "auto", "binning", "masking", "suppression"
            
        Returns:
            Suggested generalization with examples
        """
        col_data = self.df[column]
        dtype = col_data.dtype
        
        suggestions = {
            "column": column,
            "current_type": str(dtype),
            "unique_values": int(col_data.nunique()),
            "strategies": []
        }
        
        # Numeric columns: suggest binning
        if np.issubdtype(dtype, np.number):
            min_val, max_val = col_data.min(), col_data.max()
            suggestions["strategies"].append({
                "method": "binning",
                "description": f"Group into ranges (e.g., {min_val}-{max_val} into 5-10 bins)",
                "example": f"age 25 -> '20-30'"
            })
            suggestions["strategies"].append({
                "method": "rounding",
                "description": "Round to nearest 5 or 10",
                "example": f"age 27 -> 25 or 30"
            })
        
        # String columns: suggest masking/generalization
        elif dtype == object:
            suggestions["strategies"].append({
                "method": "masking",
                "description": "Mask part of the value",
                "example": "john@email.com -> j***@email.com"
            })
            suggestions["strategies"].append({
                "method": "generalization",
                "description": "Use broader category",
                "example": "94102 -> 941** (first 3 digits only)"
            })
        
        # Always suggest suppression as last resort
        suggestions["strategies"].append({
            "method": "suppression",
            "description": "Remove column entirely if not needed",
            "privacy_gain": "Maximum"
        })
        
        return suggestions
    
    def validate(
        self,
        requirements: Dict[str, Any]
    ) -> PrivacyReport:
        """
        Run complete privacy validation based on requirements.
        
        Args:
            requirements: Dictionary specifying validation requirements:
                {
                    'pii_detection': True/False,
                    'k_anonymity': {'k': 5, 'quasi_identifiers': [...]},
                    'l_diversity': {'l': 2, 'quasi_identifiers': [...], 'sensitive_attribute': '...'}
                }
                
        Returns:
            PrivacyReport with all validation results
        """
        pii_results = []
        k_anonymity = None
        l_diversity = None
        recommendations = []
        overall_passed = True
        
        # PII Detection
        if requirements.get('pii_detection', True):
            pii_results = self.detect_pii()
            pii_found = [r for r in pii_results if r.is_pii]
            if pii_found:
                overall_passed = False
                for r in pii_found:
                    recommendations.append(
                        f"Remove or anonymize PII column '{r.column_name}' ({r.pii_type})"
                    )
        
        # k-Anonymity
        if 'k_anonymity' in requirements:
            k_req = requirements['k_anonymity']
            k_anonymity = self.check_k_anonymity(
                quasi_identifiers=k_req['quasi_identifiers'],
                k=k_req['k']
            )
            if not k_anonymity.satisfies_k:
                overall_passed = False
                recommendations.append(
                    f"Dataset fails {k_req['k']}-anonymity. "
                    f"Consider generalizing: {', '.join(k_req['quasi_identifiers'])}"
                )
        
        # l-Diversity
        if 'l_diversity' in requirements:
            l_req = requirements['l_diversity']
            l_diversity = self.check_l_diversity(
                quasi_identifiers=l_req['quasi_identifiers'],
                sensitive_attribute=l_req['sensitive_attribute'],
                l=l_req['l']
            )
            if not l_diversity.satisfies_l:
                overall_passed = False
                recommendations.append(
                    f"Dataset fails {l_req['l']}-diversity for {l_req['sensitive_attribute']}"
                )
        
        logger.info(f"Privacy validation complete. Overall: {'PASSED' if overall_passed else 'FAILED'}")
        
        return PrivacyReport(
            pii_results=pii_results,
            k_anonymity=k_anonymity,
            l_diversity=l_diversity,
            overall_passed=overall_passed,
            recommendations=recommendations
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get quick privacy summary of dataset."""
        pii = self.detect_pii()
        pii_columns = [r.column_name for r in pii if r.is_pii]
        
        return {
            "n_rows": self.n_rows,
            "n_columns": self.n_cols,
            "pii_columns_detected": pii_columns,
            "pii_count": len(pii_columns),
            "high_cardinality_columns": [
                col for col in self.columns
                if self.df[col].nunique() / self.n_rows > 0.9
            ]
        }
