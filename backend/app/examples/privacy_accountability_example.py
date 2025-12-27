"""
Example script demonstrating Privacy and Accountability modules.

Shows:
1. PII detection in datasets
2. k-Anonymity validation
3. MLflow experiment tracking
4. Audit trail generation

Run from the backend directory:
    python -m app.examples.privacy_accountability_example
"""

import numpy as np
import pandas as pd
from datetime import datetime
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.validators.privacy_validator import PrivacyValidator
from app.validators.accountability_tracker import AccountabilityTracker


def create_sample_dataset() -> pd.DataFrame:
    """Create synthetic dataset with privacy concerns."""
    np.random.seed(42)
    n = 500
    
    return pd.DataFrame({
        # PII columns (should be detected)
        'email': [f"user{i}@example.com" for i in range(n)],
        'phone': [f"555-{np.random.randint(100, 999)}-{np.random.randint(1000, 9999)}" for _ in range(n)],
        'name': [f"Person {i}" for i in range(n)],
        'ssn': [f"{np.random.randint(100,999)}-{np.random.randint(10,99)}-{np.random.randint(1000,9999)}" for _ in range(n)],
        
        # Quasi-identifiers
        'age': np.random.randint(18, 80, n),
        'zip_code': np.random.choice(['10001', '10002', '10003', '90210', '60601'], n),
        'gender': np.random.choice(['M', 'F'], n),
        'occupation': np.random.choice(['Engineer', 'Teacher', 'Doctor', 'Lawyer', 'Artist'], n),
        
        # Regular features
        'income': np.random.normal(60000, 20000, n).astype(int),
        'credit_score': np.random.randint(300, 850, n),
        
        # Sensitive attribute
        'loan_approved': np.random.choice([0, 1], n)
    })


def demo_privacy_validation():
    """Demonstrate privacy validation features."""
    print("\n" + "=" * 60)
    print("PRIVACY VALIDATION DEMO")
    print("=" * 60)
    
    # Create sample data
    print("\n1. Creating sample dataset with PII...")
    df = create_sample_dataset()
    print(f"   Dataset: {len(df)} rows, {len(df.columns)} columns")
    
    # Initialize validator
    validator = PrivacyValidator(df)
    
    # Step 2: PII Detection
    print("\n2. Running PII Detection...")
    pii_results = validator.detect_pii()
    
    pii_found = [r for r in pii_results if r.is_pii]
    print(f"\n   Detected {len(pii_found)} columns with PII:")
    for r in pii_found:
        print(f"   ⚠ {r.column_name}: {r.pii_type} (confidence: {r.confidence:.0%})")
    
    # Step 3: k-Anonymity Check
    print("\n3. Checking k-Anonymity...")
    quasi_ids = ['age', 'zip_code', 'gender']
    k_result = validator.check_k_anonymity(quasi_identifiers=quasi_ids, k=5)
    
    status = "✓ PASSED" if k_result.satisfies_k else "✗ FAILED"
    print(f"\n   5-Anonymity for {quasi_ids}: {status}")
    print(f"   Minimum group size: {k_result.actual_min_k}")
    print(f"   Total groups: {k_result.total_groups}")
    
    if not k_result.satisfies_k and k_result.violating_groups:
        print(f"   Violating groups: {len(k_result.violating_groups)}")
        print(f"   Example: {k_result.violating_groups[0]}")
    
    # Step 4: l-Diversity Check
    print("\n4. Checking l-Diversity...")
    l_result = validator.check_l_diversity(
        quasi_identifiers=quasi_ids,
        sensitive_attribute='loan_approved',
        l=2
    )
    
    status = "✓ PASSED" if l_result.satisfies_l else "✗ FAILED"
    print(f"\n   2-Diversity for 'loan_approved': {status}")
    print(f"   Minimum diversity: {l_result.actual_min_l}")
    
    # Step 5: Full Validation
    print("\n5. Running Full Privacy Validation...")
    report = validator.validate({
        'pii_detection': True,
        'k_anonymity': {'k': 5, 'quasi_identifiers': quasi_ids}
    })
    
    print(f"\n   Overall: {'✓ PASSED' if report.overall_passed else '✗ FAILED'}")
    if report.recommendations:
        print("   Recommendations:")
        for rec in report.recommendations[:3]:
            print(f"   • {rec}")
    
    return df


def demo_accountability_tracking():
    """Demonstrate accountability tracking features."""
    print("\n" + "=" * 60)
    print("ACCOUNTABILITY TRACKING DEMO")
    print("=" * 60)
    
    # Initialize tracker (without MLflow for demo)
    print("\n1. Initializing Accountability Tracker...")
    tracker = AccountabilityTracker(use_mlflow=False)  # Disable MLflow for simple demo
    
    # Register a model
    print("\n2. Registering Model Version...")
    model_id = str(uuid.uuid4())
    model = tracker.register_model_version(
        model_id=model_id,
        version="1.0.0",
        model_path="./models/loan_model.pkl",
        model_type="sklearn",
        created_by="data_scientist_1",
        metadata={"algorithm": "RandomForest", "n_estimators": 100}
    )
    print(f"   Registered: {model.model_id[:8]}... v{model.version}")
    
    # Simulate validation runs
    print("\n3. Recording Validation Runs...")
    
    # Run 1: Fairness validation
    run_id = tracker.start_validation_run(
        model_name="loan_model",
        model_id=model_id,
        dataset_name="test_data_q4",
        dataset_id=str(uuid.uuid4()),
        requirement_name="ETH1-Fairness",
        requirement_id="req-001",
        principle="fairness",
        user_id="auditor_1"
    )
    tracker.log_metrics({
        "demographic_parity_ratio": 0.85,
        "equalized_odds_ratio": 0.78,
        "disparate_impact": 0.82
    })
    record1 = tracker.end_validation_run(status="passed")
    print(f"   ✓ Fairness validation: PASSED")
    
    # Run 2: Transparency validation
    run_id = tracker.start_validation_run(
        model_name="loan_model",
        model_id=model_id,
        dataset_name="test_data_q4",
        dataset_id=str(uuid.uuid4()),
        requirement_name="ETH2-Transparency",
        requirement_id="req-002",
        principle="transparency",
        user_id="auditor_1"
    )
    tracker.log_metrics({
        "shap_coverage": 1.0,
        "lime_coverage": 1.0,
        "model_card_complete": 1.0
    })
    record2 = tracker.end_validation_run(status="passed")
    print(f"   ✓ Transparency validation: PASSED")
    
    # Run 3: Privacy validation (failed)
    run_id = tracker.start_validation_run(
        model_name="loan_model",
        model_id=model_id,
        dataset_name="test_data_q4",
        dataset_id=str(uuid.uuid4()),
        requirement_name="ETH3-Privacy",
        requirement_id="req-003",
        principle="privacy",
        user_id="auditor_1"
    )
    tracker.log_metrics({
        "k_anonymity_min": 3,
        "pii_detected": 4
    })
    record3 = tracker.end_validation_run(status="failed")
    print(f"   ✗ Privacy validation: FAILED (PII detected)")
    
    # Step 4: Query History
    print("\n4. Querying Validation History...")
    history = tracker.get_validation_history(model_id=model_id)
    print(f"   Found {len(history)} validation records for this model")
    
    # Step 5: Model Lineage
    print("\n5. Getting Model Lineage...")
    lineage = tracker.get_model_lineage(model_id)
    print(f"   Model: v{lineage['model']['version']}")
    print(f"   Total validations: {lineage['summary']['total_validations']}")
    print(f"   Passed: {lineage['summary']['passed']}, Failed: {lineage['summary']['failed']}")
    print(f"   Principles validated: {lineage['summary']['principles_validated']}")
    
    # Step 6: Generate Audit Report
    print("\n6. Generating Audit Report...")
    report = tracker.generate_audit_report()
    print(f"\n   Audit Report Summary:")
    print(f"   Total validations: {report['summary']['total_validations']}")
    print(f"   Pass rate: {report['summary']['pass_rate']:.0%}")
    print(f"   By status: {report['summary']['by_status']}")
    print(f"   By principle: {report['summary']['by_principle']}")


def main():
    print("=" * 60)
    print("PRIVACY & ACCOUNTABILITY MODULE DEMO")
    print("=" * 60)
    
    # Privacy validation demo
    demo_privacy_validation()
    
    # Accountability tracking demo
    demo_accountability_tracking()
    
    print("\n" + "=" * 60)
    print("✓ Privacy & Accountability Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
