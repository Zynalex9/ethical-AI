# retrain_model.py
"""
Script to retrain the Adult Income model with proper feature compatibility.
Run this from the backend directory: python retrain_model.py
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import pickle
import os

# Paths
DATASET_PATH = r"uploads\datasets\fc34f540-4fe1-4fe8-bedc-5fd36e9defae\Adultincome_20251229_220227.csv"
MODEL_OUTPUT_PATH = r"uploads\models\fc34f540-4fe1-4fe8-bedc-5fd36e9defae\STUF_20251229_220051.pkl"

print("Loading dataset...")
df = pd.read_csv(DATASET_PATH)
print(f"Dataset shape: {df.shape}")
print(f"Columns: {list(df.columns)}")

# Separate features and target
target_column = 'income'
X = df.drop(columns=[target_column])
y = df[target_column]

print(f"\nOriginal features: {list(X.columns)}")
print(f"Number of features: {len(X.columns)}")

# Encode categorical features
print("\nEncoding categorical features...")
for col in X.select_dtypes(include=['object']).columns:
    X[col] = pd.factorize(X[col])[0]
    print(f"  Encoded: {col}")

# Encode target
print(f"\nEncoding target: {target_column}")
y_encoded = (y == '>50K').astype(int)

print(f"\nFinal X shape: {X.shape}")
print(f"Features used: {list(X.columns)}")

# Split data
print("\nSplitting data (80/20)...")
X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42
)

print(f"Training set: {X_train.shape}")
print(f"Test set: {X_test.shape}")

# Train model
print("\nTraining Logistic Regression model...")
model = LogisticRegression(max_iter=2000, random_state=42, solver='saga')
model.fit(X_train, y_train)  # Pass DataFrame directly to preserve feature names

# Test accuracy
train_score = model.score(X_train, y_train)
test_score = model.score(X_test, y_test)
print(f"Training accuracy: {train_score:.4f}")
print(f"Test accuracy: {test_score:.4f}")

# Verify model attributes
print(f"\nModel attributes:")
print(f"  n_features_in_: {model.n_features_in_}")
print(f"  feature_names_in_: {list(model.feature_names_in_)}")
print(f"  classes_: {model.classes_}")

# Save model
print(f"\nSaving model to: {MODEL_OUTPUT_PATH}")
os.makedirs(os.path.dirname(MODEL_OUTPUT_PATH), exist_ok=True)

with open(MODEL_OUTPUT_PATH, 'wb') as f:
    pickle.dump(model, f)

print("✓ Model saved successfully!")

# Verify loading
print("\nVerifying model can be loaded...")
with open(MODEL_OUTPUT_PATH, 'rb') as f:
    loaded_model = pickle.load(f)

print(f"  Loaded model type: {type(loaded_model)}")
print(f"  n_features_in_: {loaded_model.n_features_in_}")
print(f"  feature_names_in_: {list(loaded_model.feature_names_in_)}")

# Test prediction
print("\nTesting prediction on first 5 samples...")
predictions = loaded_model.predict(X.iloc[:5])
print(f"  Predictions: {predictions}")
print(f"  Actual: {y_encoded.values[:5]}")

# Verify predictions work with numpy arrays too
print("\nTesting with numpy array (validation will use this)...")
predictions_np = loaded_model.predict(X.iloc[:5].values)
print(f"  Predictions: {predictions_np}")

print("\n✓ All checks passed! Model is ready for validation.")
print(f"\nNOTE: Make sure to restart the Celery worker after running this script!")