"""
Example script demonstrating the Fairness Validator.

This script shows how to:
1. Load a trained model using UniversalModelLoader
2. Validate it for fairness using FairnessValidator
3. Generate comprehensive fairness reports

Run from the backend directory:
    python -m app.examples.fairness_example
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import joblib
import os

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.validators.fairness_validator import FairnessValidator
from app.services.model_loader import UniversalModelLoader


def create_sample_data() -> tuple:
    """
    Create synthetic dataset with known bias for demonstration.
    
    Returns:
        X, y, sensitive_features as numpy arrays
    """
    np.random.seed(42)
    n_samples = 1000
    
    # Features: income, credit_score, age, employment_years
    income = np.random.normal(50000, 15000, n_samples)
    credit_score = np.random.normal(650, 100, n_samples)
    age = np.random.normal(35, 10, n_samples)
    employment_years = np.random.normal(5, 3, n_samples)
    
    # Sensitive feature: gender (0=female, 1=male)
    gender = np.random.binomial(1, 0.5, n_samples)
    
    # Create biased target: males have higher approval rate
    # This simulates historical bias in the data
    base_score = (
        0.3 * (income / 100000) +
        0.3 * (credit_score / 850) +
        0.2 * (age / 60) +
        0.2 * (employment_years / 10)
    )
    
    # Add gender bias: males get a boost
    biased_score = base_score + 0.15 * gender
    
    # Convert to binary target
    threshold = np.percentile(biased_score, 50)
    y = (biased_score > threshold).astype(int)
    
    # Create feature matrix
    X = np.column_stack([income, credit_score, age, employment_years])
    
    return X, y, gender


def main():
    print("=" * 60)
    print("FAIRNESS VALIDATION DEMO")
    print("=" * 60)
    
    # Step 1: Create sample data
    print("\n1. Creating synthetic biased dataset...")
    X, y, gender = create_sample_data()
    print(f"   Dataset: {len(X)} samples, {X.shape[1]} features")
    print(f"   Gender distribution: Female={sum(gender==0)}, Male={sum(gender==1)}")
    print(f"   Approval rate: {y.mean():.1%}")
    
    # Step 2: Train a model
    print("\n2. Training logistic regression model...")
    X_train, X_test, y_train, y_test, gender_train, gender_test = train_test_split(
        X, y, gender, test_size=0.3, random_state=42
    )
    
    model = LogisticRegression(random_state=42)
    model.fit(X_train, y_train)
    
    # Get predictions
    y_pred = model.predict(X_test)
    accuracy = (y_pred == y_test).mean()
    print(f"   Test accuracy: {accuracy:.2%}")
    
    # Step 3: Validate fairness
    print("\n3. Running fairness validation...")
    validator = FairnessValidator(
        y_true=y_test,
        y_pred=y_pred,
        sensitive_features=np.where(gender_test == 0, 'Female', 'Male')
    )
    
    # Run full validation
    report = validator.validate_all(
        thresholds={
            'demographic_parity_ratio': 0.8,
            'equalized_odds_ratio': 0.8,
            'disparate_impact_ratio': 0.8
        },
        include_visualizations=False  # Disable for CLI demo
    )
    
    # Step 4: Display results
    print("\n" + "=" * 60)
    print("FAIRNESS REPORT")
    print("=" * 60)
    
    print(f"\nGroups analyzed: {', '.join(report.groups)}")
    print(f"Sample sizes: {report.sample_sizes}")
    
    print("\n--- METRICS ---")
    for metric in report.metrics:
        status = "✓ PASS" if metric.passed else "✗ FAIL"
        print(f"\n{metric.metric_name}:")
        print(f"  Value: {metric.overall_value:.3f} (threshold: {metric.threshold:.2f}) [{status}]")
        if isinstance(list(metric.by_group.values())[0], dict):
            for group, values in metric.by_group.items():
                print(f"  {group}: TPR={values['tpr']:.2%}, FPR={values['fpr']:.2%}")
        else:
            for group, value in metric.by_group.items():
                print(f"  {group}: {value:.2%}")
    
    print("\n--- CONFUSION MATRICES BY GROUP ---")
    for cm in report.confusion_matrices:
        print(f"\n{cm.group_name}:")
        print(f"  TP={cm.tp}, FP={cm.fp}, TN={cm.tn}, FN={cm.fn}")
        print(f"  Accuracy={cm.accuracy:.2%}, TPR={cm.tpr:.2%}, FPR={cm.fpr:.2%}")
    
    print("\n" + "=" * 60)
    overall = "✓ PASSED" if report.overall_passed else "✗ FAILED"
    print(f"OVERALL FAIRNESS: {overall}")
    print("=" * 60)
    
    # Step 5: Save model for later testing
    print("\n4. Saving model for later testing...")
    os.makedirs("./test_models", exist_ok=True)
    model_path = "./test_models/sample_model.pkl"
    joblib.dump(model, model_path)
    print(f"   Model saved to: {model_path}")
    
    # Step 6: Demonstrate model loading
    print("\n5. Testing UniversalModelLoader...")
    loaded_model = UniversalModelLoader.load(model_path)
    print(f"   Model type: {loaded_model.model_type}")
    
    metadata = UniversalModelLoader.get_model_metadata(loaded_model)
    print(f"   Model class: {metadata.get('model_class')}")
    
    # Verify predictions match
    y_pred_loaded = loaded_model.predict(X_test)
    match = (y_pred == y_pred_loaded).all()
    print(f"   Predictions match original: {match}")
    
    print("\n✓ Demo complete!")


if __name__ == "__main__":
    main()
