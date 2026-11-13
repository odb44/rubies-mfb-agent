"""Load and execute the versioned synthetic loan delinquency model V2."""

import json
import os
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from rubies_loan_model.schemas_v2 import (
    FEATURE_SCHEMA_VERSION,
    LoanApplicantInputV2,
    LoanModelPredictionV2,
)

DEFAULT_MODEL_VERSION = "loan-logreg-v2"


def find_repository_root() -> Path:
    """Locate the repository root without relying on the current directory."""

    for parent in Path(__file__).resolve().parents:
        if (parent / "artifacts" / "loan_model").is_dir():
            return parent

    raise FileNotFoundError("Could not locate the repository's artifacts/loan_model directory.")


class LoanModelInferenceV2:
    """Inference wrapper for the synthetic loan delinquency model V2."""

    def __init__(
        self,
        model_version: str | None = None,
        repository_root: Path | None = None,
    ) -> None:
        self.model_version = model_version or os.getenv(
            "RUBIES_LOAN_MODEL_V2_VERSION",
            DEFAULT_MODEL_VERSION,
        )

        if not self.model_version or Path(self.model_version).name != self.model_version:
            raise ValueError("Invalid model version.")

        self.repository_root = repository_root or find_repository_root()

        manifest_path = (
            self.repository_root
            / "artifacts"
            / "loan_model"
            / "manifests"
            / f"{self.model_version}.json"
        )

        if not manifest_path.is_file():
            raise FileNotFoundError(f"Model manifest not found: {manifest_path}")

        self.manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))

        if self.manifest.get("model_version") != self.model_version:
            raise ValueError("Manifest model_version does not match the requested version.")

        if self.manifest.get("feature_schema_version") != (FEATURE_SCHEMA_VERSION):
            raise ValueError("Model feature schema version is incompatible.")

        artifact_relative_path = Path(self.manifest["artifact_location"])

        if artifact_relative_path.is_absolute() or ".." in artifact_relative_path.parts:
            raise ValueError("Manifest contains an unsafe artifact path.")

        artifact_path = self.repository_root / artifact_relative_path

        if not artifact_path.is_file():
            raise FileNotFoundError(f"Model artifact not found: {artifact_path}")

        self.model = joblib.load(artifact_path)

        self.input_features = self.manifest.get(
            "input_features",
            [],
        )

        if not self.input_features:
            raise ValueError("Manifest does not define input_features.")

        self.target_mapping = self.manifest.get(
            "target_mapping",
            {},
        )

        if self.target_mapping != {
            "NOT_DELINQUENT": 0,
            "DELINQUENT": 1,
        }:
            raise ValueError("Unexpected target mapping in model manifest.")

        selection = self.manifest.get("selection", {})

        self.classification_threshold = selection.get("selected_threshold")

        if (
            isinstance(self.classification_threshold, bool)
            or not isinstance(self.classification_threshold, (int, float))
            or not 0 <= self.classification_threshold <= 1
        ):
            raise ValueError("Manifest contains an invalid classification threshold.")

        if self.manifest.get("synthetic_data") is not True:
            raise ValueError("This inference service only supports the synthetic V2 model.")

    def predict(
        self,
        applicant: LoanApplicantInputV2,
    ) -> LoanModelPredictionV2:
        """Predict 90-day delinquency risk without making a lending decision."""

        if not isinstance(applicant, LoanApplicantInputV2):
            raise TypeError("applicant must be a LoanApplicantInputV2 instance.")

        features = applicant.to_model_features()

        missing_features = set(self.input_features) - set(features)

        if missing_features:
            raise ValueError(f"Required model features are missing: {sorted(missing_features)}")

        frame = pd.DataFrame(
            [{name: features[name] for name in self.input_features}],
            columns=self.input_features,
        )

        probabilities = self.model.predict_proba(frame)[0]

        classifier_classes = list(self.model.named_steps["classifier"].classes_)

        class_probabilities = {
            int(label): float(probability)
            for label, probability in zip(
                classifier_classes,
                probabilities,
                strict=True,
            )
        }

        probability_not_delinquent = class_probabilities.get(0)
        probability_delinquent = class_probabilities.get(1)

        if probability_not_delinquent is None or probability_delinquent is None:
            raise ValueError("Model classes do not match the expected target mapping.")

        if not (0 <= probability_delinquent <= 1 and 0 <= probability_not_delinquent <= 1):
            raise ValueError("Model returned invalid probabilities.")

        predicted_delinquent = int(probability_delinquent >= self.classification_threshold)

        return LoanModelPredictionV2(
            model_version=self.model_version,
            predicted_delinquent=predicted_delinquent,
            probability_delinquent=probability_delinquent,
            probability_not_delinquent=probability_not_delinquent,
        )
