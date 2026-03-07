"""
Generate known-good model and dataset assets for upload testing.

Outputs:
- uploads_test_assets/sample_dataset.csv
- uploads_test_assets/sample_model.pkl
- uploads_test_assets/sample_model.joblib
- uploads_test_assets/sample_model.pickle
"""

from pathlib import Path
import pickle

import joblib
import numpy as np
import pandas as pd

from app.examples.dummy_model import ToyBinaryModel


def main() -> None:
    base_dir = Path(__file__).resolve().parent / "uploads_test_assets"
    base_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(42)
    n_rows = 1000
    n_features = 8
    X = rng.normal(size=(n_rows, n_features))

    df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(n_features)])
    # Add a synthetic sensitive attribute for fairness testing
    df["gender"] = (df["feature_0"] > df["feature_0"].median()).map({True: "M", False: "F"})

    weights = np.array([0.9, -0.6, 0.4, 0.3, -0.2, 0.1, 0.5, -0.4])
    logits = X @ weights + 0.15
    probs = 1.0 / (1.0 + np.exp(-logits))
    df["target"] = (probs >= 0.5).astype(int)

    dataset_path = base_dir / "sample_dataset.csv"
    df.to_csv(dataset_path, index=False)

    model = ToyBinaryModel(weights=weights, bias=0.15)

    # Save in supported formats
    joblib.dump(model, base_dir / "sample_model.joblib")
    with open(base_dir / "sample_model.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(base_dir / "sample_model.pickle", "wb") as f:
        pickle.dump(model, f)

    print("Generated test assets:")
    print(f"- {dataset_path}")
    print(f"- {base_dir / 'sample_model.pkl'}")
    print(f"- {base_dir / 'sample_model.joblib'}")
    print(f"- {base_dir / 'sample_model.pickle'}")
    print("\nUpload tips:")
    print("- Dataset sensitive_attributes: gender")
    print("- Dataset target_column: target")


if __name__ == "__main__":
    main()
