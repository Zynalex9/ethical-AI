"""
Example script demonstrating the Explainability Engine.

This script shows how to:
1. Load a trained model
2. Generate SHAP global and local explanations
3. Generate LIME explanations
4. Create model cards for documentation
5. Validate transparency requirements

Run from the backend directory:
    python -m app.examples.transparency_example
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.datasets import make_classification
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.validators.explainability_engine import ExplainabilityEngine


def main():
    print("=" * 60)
    print("TRANSPARENCY / EXPLAINABILITY DEMO")
    print("=" * 60)
    
    # Step 1: Create synthetic dataset
    print("\n1. Creating synthetic classification dataset...")
    X, y = make_classification(
        n_samples=500,
        n_features=10,
        n_informative=5,
        n_redundant=2,
        n_classes=2,
        random_state=42
    )
    
    feature_names = [
        "credit_score", "annual_income", "debt_ratio", "employment_years",
        "loan_amount", "interest_rate", "loan_term", "num_accounts",
        "credit_utilization", "recent_inquiries"
    ]
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )
    
    print(f"   Training set: {len(X_train)} samples")
    print(f"   Test set: {len(X_test)} samples")
    print(f"   Features: {len(feature_names)}")
    
    # Step 2: Train model
    print("\n2. Training Random Forest model...")
    model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    model.fit(X_train, y_train)
    
    accuracy = model.score(X_test, y_test)
    print(f"   Test accuracy: {accuracy:.2%}")
    
    # Step 3: Initialize Explainability Engine
    print("\n3. Initializing Explainability Engine...")
    engine = ExplainabilityEngine(
        model=model,
        X_train=X_train,
        feature_names=feature_names,
        class_names=["Rejected", "Approved"],
        model_name="Loan Approval Model",
        model_description="Random Forest classifier for loan approval decisions"
    )
    
    # Step 4: Generate Global SHAP Explanation
    print("\n4. Generating Global SHAP Explanation...")
    global_exp = engine.explain_global_shap(X_test, max_samples=100)
    
    print("\n   Feature Importance (Top 5):")
    for fi in global_exp.top_features(5):
        print(f"   {fi.rank}. {fi.feature_name}: {fi.importance:.4f}")
    
    # Step 5: Generate Local SHAP Explanations
    print("\n5. Generating Local SHAP Explanations...")
    local_exps = engine.explain_local_shap(X_test, [0, 1, 2])
    
    for exp in local_exps:
        print(f"\n   Instance {exp.instance_index}:")
        print(f"   Prediction: {'Approved' if exp.prediction == 1 else 'Rejected'} ({exp.prediction_probability:.2%})")
        
        # Top 3 contributions
        sorted_contrib = sorted(
            exp.feature_contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:3]
        print("   Top contributing features:")
        for name, value in sorted_contrib:
            direction = "↑" if value > 0 else "↓"
            print(f"     {direction} {name}: {value:+.4f}")
    
    # Step 6: Generate LIME Explanation
    print("\n6. Generating LIME Explanation...")
    lime_exps = engine.explain_local_lime(X_test, [0])
    
    exp = lime_exps[0]
    print(f"   Instance 0 (LIME):")
    print(f"   Prediction: {'Approved' if exp.prediction == 1 else 'Rejected'}")
    print("   Feature contributions:")
    for name, value in list(exp.feature_contributions.items())[:5]:
        direction = "↑" if value > 0 else "↓"
        print(f"     {direction} {name}: {value:+.4f}")
    
    # Step 7: Generate Model Card
    print("\n7. Generating Model Card...")
    model_card = engine.generate_model_card(X_test, y_test)
    
    print("\n   Model Card Summary:")
    print(f"   Name: {model_card['model_details']['name']}")
    print(f"   Type: {model_card['model_details']['model_type']}")
    print(f"   Features: {model_card['model_details']['n_features']}")
    print(f"   Performance:")
    for metric, value in model_card['performance_metrics'].items():
        print(f"     {metric}: {value:.4f}")
    
    # Step 8: Validate Transparency Requirements
    print("\n8. Validating Transparency Requirements...")
    validation = engine.validate(X_test, y_test, {
        "global_explanation_required": True,
        "local_explanation_required": True,
        "min_features_documented": 5,
        "model_card_required": True
    })
    
    print(f"\n   Overall: {'✓ PASSED' if validation['passed'] else '✗ FAILED'}")
    for check in validation['checks']:
        status = "✓" if check['passed'] else "✗"
        print(f"   {status} {check['name']}: {check['details']}")
    
    # Step 9: Generate Full Report
    print("\n9. Generating Full Transparency Report...")
    report = engine.generate_report(
        X_test, y_test,
        n_local_samples=3,
        include_visualizations=False  # Disable for CLI demo
    )
    
    print(f"\n   Report Summary:")
    print(f"   Global explanation: {len(report.global_explanation.feature_importances)} features")
    print(f"   Local explanations: {len(report.local_explanations)} instances")
    print(f"   Model card: Generated")
    print(f"   Validation: {'PASSED' if report.validation_passed else 'FAILED'}")
    
    print("\n" + "=" * 60)
    print("✓ Transparency Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
