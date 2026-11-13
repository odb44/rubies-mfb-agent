"""Load a versioned historical loan model and produce predictions."""

import json
import os
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from rubies_loan_model.schemas import LoanApplicantInput, LoanModelPrediction

DEFAULT_MODEL_VERSION = "loan-logreg-v1"


def find_repository_root() -> Path:
    """Locate the repository root without relying on the current directory."""

    for parent in Path(__file__).resolve().parents:
        if (parent / "artifacts" / "loan_model").is_dir():
            return parent

    raise FileNotFoundError("Could not locate the repository's artifacts/loan_model directory.")


class LoanModelInference:
    """Inference wrapper for the versioned historical loan model."""

    def __init__(
        self,
        model_version: str | None = None,
        repository_root: Path | None = None,
    ) -> None:
        self.model_version = model_version or os.getenv(
            "RUBIES_LOAN_MODEL_VERSION",
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

        artifact_relative_path = Path(self.manifest["artifact_location"])

        if artifact_relative_path.is_absolute() or ".." in artifact_relative_path.parts:
            raise ValueError("Manifest contains an unsafe artifact path.")

        artifact_path = self.repository_root / artifact_relative_path

        if not artifact_path.is_file():
            raise FileNotFoundError(f"Model artifact not found: {artifact_path}")

        self.model = joblib.load(artifact_path)

        self.input_features = self.manifest.get("input_features", [])

        if not self.input_features:
            raise ValueError("Manifest does not define input_features.")

    def predict(self, applicant: LoanApplicantInput) -> LoanModelPrediction:
        """Return a historical-label prediction without making a lending decision."""

        features = applicant.to_model_features()

        missing_features = set(self.input_features) - set(features)
        if missing_features:
            raise ValueError(f"Required model features are missing: {sorted(missing_features)}")

        frame = pd.DataFrame(
            [{name: features[name] for name in self.input_features}],
            columns=self.input_features,
        )

        predicted_class = self.model.predict(frame)[0]
        probabilities = self.model.predict_proba(frame)[0]
        classes = list(self.model.named_steps["classifier"].classes_)

        class_probabilities = {
            str(label): float(probability)
            for label, probability in zip(classes, probabilities, strict=True)
        }

        target_mapping = self.manifest.get("target_mapping", {"N": 0, "Y": 1})

        # The manifest maps historical labels to encoded classifier labels.
        encoded_to_label = {str(encoded): label for label, encoded in target_mapping.items()}

        predicted_label = encoded_to_label.get(str(predicted_class))

        if predicted_label not in {"Y", "N"}:
            raise ValueError(
                f"Unexpected model output {predicted_class!r}; "
                f"manifest mapping is {target_mapping!r}."
            )

        probability_no = class_probabilities.get(str(target_mapping["N"]))
        probability_yes = class_probabilities.get(str(target_mapping["Y"]))

        if probability_no is None or probability_yes is None:
            raise ValueError(
                f"Model classes {classes!r} do not match manifest mapping {target_mapping!r}."
            )
        return LoanModelPrediction(
            model_version=self.model_version,
            predicted_historical_status=predicted_label,
            probability_historical_no=probability_no,
            probability_historical_yes=probability_yes,
        )
