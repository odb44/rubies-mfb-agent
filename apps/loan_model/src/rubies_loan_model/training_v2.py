"""Train and compare recall-oriented loan delinquency models for V2.

Models:
- Logistic Regression
- Random Forest

Selection:
- Target validation recall: 70%
- Threshold selection: highest precision among thresholds meeting
  the recall target, with F2 as tie-breaker.
- If no threshold meets the recall target, select the highest F2.

The final test set is not used for model or threshold selection.
"""

import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from rubies_loan_model.schemas_v2 import FEATURE_SCHEMA_VERSION

# ============================================================
# Configuration
# ============================================================

RANDOM_STATE = 42

TARGET_COLUMN = "delinquent"

MINIMUM_TARGET_RECALL = 0.70

THRESHOLD_CANDIDATES = [
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.45,
    0.50,
    0.55,
    0.60,
]

DEFAULT_THRESHOLD = 0.50

# ============================================================
# Feature definitions
# ============================================================

CATEGORICAL_FEATURES = [
    "employment_type",
    "repayment_frequency",
]

NUMERIC_FEATURES = [
    "monthly_income_ngn",
    "monthly_expenses_ngn",
    "existing_monthly_debt_ngn",
    "requested_amount_ngn",
    "term_months",
    "previous_loan_count",
    "previous_repayment_rate",
    "previous_default_count",
    "disposable_income_ngn",
    "estimated_monthly_repayment_ngn",
    "repayment_to_income_ratio",
]

INPUT_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

EXPECTED_COLUMNS = set(INPUT_FEATURES + [TARGET_COLUMN])


# ============================================================
# Repository and artifact utilities
# ============================================================


def find_repository_root() -> Path:
    """Locate the repository root."""

    for parent in Path(__file__).resolve().parents:
        if (parent / "artifacts" / "loan_model").is_dir():
            return parent

    raise FileNotFoundError("Could not locate artifacts/loan_model in the repository.")


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a file."""

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


# ============================================================
# Preprocessing
# ============================================================


def build_preprocessor(
    scale_numeric: bool,
) -> ColumnTransformer:
    """Build preprocessing for numeric and categorical features."""

    numeric_steps = [
        (
            "imputer",
            SimpleImputer(strategy="median"),
        ),
    ]

    if scale_numeric:
        numeric_steps.append(
            (
                "scaler",
                StandardScaler(),
            )
        )

    numeric_pipeline = Pipeline(numeric_steps)

    categorical_pipeline = Pipeline(
        [
            (
                "imputer",
                SimpleImputer(strategy="most_frequent"),
            ),
            (
                "onehot",
                OneHotEncoder(handle_unknown="ignore"),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            (
                "numeric",
                numeric_pipeline,
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                categorical_pipeline,
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


# ============================================================
# Candidate models
# ============================================================


def build_candidates() -> dict[str, Pipeline]:
    """Create comparable model pipelines."""

    logistic_regression = Pipeline(
        [
            (
                "preprocessing",
                build_preprocessor(scale_numeric=True),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=2_000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )

    random_forest = Pipeline(
        [
            (
                "preprocessing",
                build_preprocessor(scale_numeric=False),
            ),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=400,
                    min_samples_leaf=5,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    return {
        "loan-logreg-v2": logistic_regression,
        "loan-rf-v2": random_forest,
    }


# ============================================================
# Evaluation metrics
# ============================================================


def calculate_f2(
    precision: float,
    recall: float,
) -> float:
    """Calculate F2, weighting recall more heavily than precision."""

    denominator = (4 * precision) + recall

    if denominator == 0:
        return 0.0

    return (5 * precision * recall) / denominator


def evaluate_model(
    model: Pipeline,
    features: pd.DataFrame,
    target: pd.Series,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """Calculate classification and probability metrics."""

    probabilities = model.predict_proba(features)[:, 1]

    predictions = (probabilities >= threshold).astype(int)

    matrix = confusion_matrix(
        target,
        predictions,
        labels=[0, 1],
    )

    precision = float(
        precision_score(
            target,
            predictions,
            zero_division=0,
        )
    )

    recall = float(
        recall_score(
            target,
            predictions,
            zero_division=0,
        )
    )

    return {
        "accuracy": float(
            accuracy_score(
                target,
                predictions,
            )
        ),
        "precision": precision,
        "recall": recall,
        "f1": float(
            f1_score(
                target,
                predictions,
                zero_division=0,
            )
        ),
        "f2": calculate_f2(
            precision,
            recall,
        ),
        "roc_auc": float(
            roc_auc_score(
                target,
                probabilities,
            )
        ),
        "brier_score": float(
            brier_score_loss(
                target,
                probabilities,
            )
        ),
        "confusion_matrix": {
            "labels": [
                "NOT_DELINQUENT",
                "DELINQUENT",
            ],
            "matrix": matrix.tolist(),
        },
        "classification_threshold": threshold,
    }


# ============================================================
# Threshold optimisation
# ============================================================


def evaluate_thresholds(
    model: Pipeline,
    features: pd.DataFrame,
    target: pd.Series,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Evaluate thresholds and select a recall-oriented threshold."""

    probabilities = model.predict_proba(features)[:, 1]

    results = []

    for threshold in THRESHOLD_CANDIDATES:
        predictions = (probabilities >= threshold).astype(int)

        precision = float(
            precision_score(
                target,
                predictions,
                zero_division=0,
            )
        )

        recall = float(
            recall_score(
                target,
                predictions,
                zero_division=0,
            )
        )

        f1 = float(
            f1_score(
                target,
                predictions,
                zero_division=0,
            )
        )

        f2 = calculate_f2(
            precision,
            recall,
        )

        results.append(
            {
                "threshold": threshold,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "f2": f2,
            }
        )

    # Prefer thresholds achieving the minimum recall target.
    qualifying = [result for result in results if result["recall"] >= MINIMUM_TARGET_RECALL]

    if qualifying:
        selected = max(
            qualifying,
            key=lambda result: (
                result["precision"],
                result["f2"],
            ),
        )

        selection_reason = (
            "Highest precision among thresholds meeting the minimum validation recall target."
        )

    else:
        selected = max(
            results,
            key=lambda result: (
                result["f2"],
                result["recall"],
            ),
        )

        selection_reason = (
            "No threshold achieved the minimum validation "
            "recall target. Selected the highest validation F2."
        )

    selected = {
        **selected,
        "minimum_recall_target": MINIMUM_TARGET_RECALL,
        "recall_target_achieved": (selected["recall"] >= MINIMUM_TARGET_RECALL),
        "selection_reason": selection_reason,
    }

    return results, selected


# ============================================================
# Dataset validation
# ============================================================


def load_and_validate_dataset(
    dataset_path: Path,
) -> pd.DataFrame:
    """Load the dataset and validate the training requirements."""

    if not dataset_path.is_file():
        raise FileNotFoundError(f"Training dataset not found: {dataset_path}")

    data = pd.read_csv(dataset_path)

    missing_columns = EXPECTED_COLUMNS - set(data.columns)

    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing_columns)}")

    if data.empty:
        raise ValueError("Training dataset cannot be empty.")

    if data.duplicated().any():
        raise ValueError("Training dataset contains duplicate rows.")

    if data[INPUT_FEATURES + [TARGET_COLUMN]].isna().any().any():
        raise ValueError("Dataset contains missing values in required columns.")

    if set(data[TARGET_COLUMN].unique()) != {0, 1}:
        raise ValueError("Target column must contain both binary classes 0 and 1.")

    return data


# ============================================================
# Training and model selection
# ============================================================


def train_and_evaluate_v2(
    repository_root: Path | None = None,
) -> dict[str, Any]:
    """Train candidates, select a model and evaluate on held-out test data."""

    root = repository_root or find_repository_root()

    dataset_path = root / "data" / "model" / "training" / "synthetic_loan_delinquency_v2.csv"

    data = load_and_validate_dataset(dataset_path)

    # Explicit feature selection prevents target leakage.
    X = data[INPUT_FEATURES].copy()

    y = data[TARGET_COLUMN].astype(int)

    # --------------------------------------------------------
    # Stratified data splitting
    # --------------------------------------------------------

    # First split: 85% development and 15% final test.
    X_development, X_test, y_development, y_test = train_test_split(
        X,
        y,
        test_size=0.15,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    # Split the development set into 70% train and 15% validation
    # of the complete dataset.
    validation_fraction = 0.15 / 0.85

    X_train, X_validation, y_train, y_validation = train_test_split(
        X_development,
        y_development,
        test_size=validation_fraction,
        random_state=RANDOM_STATE,
        stratify=y_development,
    )

    print("\n========== DATA SPLIT ==========")

    print(f"Training records:   {len(X_train):,}")
    print(f"Validation records: {len(X_validation):,}")
    print(f"Test records:       {len(X_test):,}")

    print(f"Training prevalence: {y_train.mean():.2%}")

    print(f"Validation prevalence: {y_validation.mean():.2%}")

    print(f"Test prevalence: {y_test.mean():.2%}")

    # --------------------------------------------------------
    # Train candidate models
    # --------------------------------------------------------

    candidates = build_candidates()

    validation_results: dict[str, dict[str, Any]] = {}

    threshold_results: dict[str, list[dict[str, Any]]] = {}

    selected_thresholds: dict[str, dict[str, Any]] = {}

    for version, model in candidates.items():
        print(f"\n========== TRAINING {version} ==========")

        model.fit(
            X_train,
            y_train,
        )

        threshold_table, selected_threshold = evaluate_thresholds(
            model,
            X_validation,
            y_validation,
        )

        threshold_results[version] = threshold_table

        selected_thresholds[version] = selected_threshold

        selected_operating_point = evaluate_model(
            model,
            X_validation,
            y_validation,
            threshold=selected_threshold["threshold"],
        )

        validation_results[version] = selected_operating_point

        print("\nThreshold comparison:")

        for result in threshold_table:
            print(
                f"Threshold={result['threshold']:.2f} | "
                f"Precision={result['precision']:.4f} | "
                f"Recall={result['recall']:.4f} | "
                f"F1={result['f1']:.4f} | "
                f"F2={result['f2']:.4f}"
            )

        print("\nSelected operating point:")

        print(f"Threshold: {selected_threshold['threshold']:.2f}")

        print(f"Precision: {selected_threshold['precision']:.4f}")

        print(f"Recall: {selected_threshold['recall']:.4f}")

        print(f"F2: {selected_threshold['f2']:.4f}")

        print(f"Recall target achieved: {selected_threshold['recall_target_achieved']}")

    # --------------------------------------------------------
    # Select the winning model using validation F2
    # --------------------------------------------------------

    selected_version = max(
        validation_results,
        key=lambda version: (
            validation_results[version]["f2"],
            validation_results[version]["roc_auc"],
        ),
    )

    selected_model = candidates[selected_version]

    selected_threshold = selected_thresholds[selected_version]

    final_threshold = selected_threshold["threshold"]

    # --------------------------------------------------------
    # Final evaluation on untouched test data
    # --------------------------------------------------------

    test_results = evaluate_model(
        selected_model,
        X_test,
        y_test,
        threshold=final_threshold,
    )

    # --------------------------------------------------------
    # Model artifact
    # --------------------------------------------------------

    if selected_version == "loan-logreg-v2":
        model_type = "scikit-learn Pipeline: preprocessing + LogisticRegression"

    else:
        model_type = "scikit-learn Pipeline: preprocessing + RandomForestClassifier"

    artifact_relative_path = (
        Path("artifacts") / "loan_model" / "versions" / selected_version / "model.joblib"
    )

    artifact_path = root / artifact_relative_path

    artifact_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        selected_model,
        artifact_path,
    )

    # --------------------------------------------------------
    # Model manifest
    # --------------------------------------------------------

    manifest = {
        "model_version": selected_version,
        "artifact_location": (artifact_relative_path.as_posix()),
        "artifact_format": "joblib",
        "model_type": model_type,
        "target": TARGET_COLUMN,
        "target_mapping": {
            "NOT_DELINQUENT": 0,
            "DELINQUENT": 1,
        },
        "target_interpretation": (
            "Loan reaches at least 30 days past due within 90 days of the repayment schedule."
        ),
        "training_data_path": (dataset_path.relative_to(root).as_posix()),
        "training_data_sha256": (calculate_sha256(dataset_path)),
        "training_data_rows": len(data),
        "feature_schema_version": (FEATURE_SCHEMA_VERSION),
        "input_features": INPUT_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "excluded_outcome_features": [
            "days_past_due",
            "delinquency_within_90_days",
            "delinquent",
        ],
        "split": {
            "train_rows": len(X_train),
            "validation_rows": len(X_validation),
            "test_rows": len(X_test),
            "random_state": RANDOM_STATE,
        },
        "selection": {
            "metric": "validation F2",
            "threshold_metric": (
                "highest precision among thresholds meeting minimum validation recall"
            ),
            "minimum_validation_recall": (MINIMUM_TARGET_RECALL),
            "selected_model": selected_version,
            "selected_threshold": final_threshold,
            "recall_target_achieved": (selected_threshold["recall_target_achieved"]),
            "selection_reason": (selected_threshold["selection_reason"]),
        },
        "threshold_candidates": THRESHOLD_CANDIDATES,
        "validation_results": validation_results,
        "threshold_results": threshold_results,
        "selected_threshold_details": selected_threshold,
        "test_results": test_results,
        "created_at_utc": (datetime.now(UTC).isoformat()),
        "python_version": platform.python_version(),
        "scikit_learn_version": sklearn.__version__,
        "synthetic_data": True,
        "assumed_target_prevalence": 0.20,
        "observed_target_prevalence": float(y.mean()),
        "intended_use": ("Synthetic capstone demonstration only"),
        "limitations": [
            "Training data is entirely synthetic.",
            "Target prevalence is a modelling assumption, not an observed portfolio rate.",
            "Synthetic risk relationships were defined by the data generator.",
            "The model is not validated on actual Rubies MFB loan performance.",
            "The model must not independently approve, reject, or disburse loans.",
            "Repayment estimates exclude interest and fees.",
            "Classification threshold is an experimental "
            "monitoring threshold, not a lending policy.",
            "Applicants without previous loans have a "
            "synthetically assigned neutral repayment history.",
        ],
    }

    manifest_path = root / "artifacts" / "loan_model" / "manifests" / f"{selected_version}.json"

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Training report
    # --------------------------------------------------------

    report = {
        "dataset": {
            "path": dataset_path.relative_to(root).as_posix(),
            "rows": len(data),
            "target_prevalence": float(y.mean()),
            "sha256": calculate_sha256(dataset_path),
        },
        "split": {
            "train_rows": len(X_train),
            "validation_rows": len(X_validation),
            "test_rows": len(X_test),
        },
        "candidate_validation_results": validation_results,
        "threshold_results": threshold_results,
        "selected_thresholds": selected_thresholds,
        "selected_model": selected_version,
        "selected_threshold": final_threshold,
        "selected_model_test_results": test_results,
    }

    report_path = (
        root / "artifacts" / "loan_model" / "reports" / "loan-model-v2-training-report.json"
    )

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Final console summary
    # --------------------------------------------------------

    print("\n========== MODEL COMPARISON ==========")

    for version, metrics in validation_results.items():
        print(f"\n{version}")

        print(f"Threshold: {metrics['classification_threshold']:.2f}")

        print(f"Precision: {metrics['precision']:.4f}")

        print(f"Recall:    {metrics['recall']:.4f}")

        print(f"F1:        {metrics['f1']:.4f}")

        print(f"F2:        {metrics['f2']:.4f}")

        print(f"ROC-AUC:   {metrics['roc_auc']:.4f}")

        print(f"Brier:     {metrics['brier_score']:.4f}")

    print("\n========== SELECTED MODEL ==========")

    print(f"Model: {selected_version}")

    print(f"Threshold: {final_threshold:.2f}")

    print(f"Validation recall target achieved: {selected_threshold['recall_target_achieved']}")

    print("\n========== FINAL TEST RESULTS ==========")

    for metric, value in test_results.items():
        print(f"{metric}: {value}")

    print("\n========== SAVED ARTIFACTS ==========")

    print(f"Model artifact: {artifact_path}")

    print(f"Manifest: {manifest_path}")

    print(f"Training report: {report_path}")

    return {
        "selected_model": selected_version,
        "selected_threshold": final_threshold,
        "validation_results": validation_results,
        "threshold_results": threshold_results,
        "test_results": test_results,
        "artifact_path": artifact_path,
        "manifest_path": manifest_path,
        "report_path": report_path,
    }


if __name__ == "__main__":
    train_and_evaluate_v2()
