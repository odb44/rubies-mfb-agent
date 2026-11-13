import numpy as np
import pandas as pd
import pytest
from rubies_loan_model import training_v2 as training


def make_dataset(rows=100):
    """Create a small valid dataset for training validation tests."""

    rng = np.random.default_rng(42)

    income = rng.integers(100_000, 800_000, rows)
    expenses = income * rng.uniform(0.2, 0.7, rows)
    debt = income * rng.uniform(0.0, 0.3, rows)
    amount = rng.integers(20_000, 500_000, rows)
    term = rng.integers(1, 13, rows)

    data = pd.DataFrame(
        {
            "employment_type": rng.choice(
                ["SALARIED", "SELF_EMPLOYED", "BUSINESS_OWNER"],
                rows,
            ),
            "repayment_frequency": rng.choice(
                ["WEEKLY", "BIWEEKLY", "MONTHLY"],
                rows,
            ),
            "monthly_income_ngn": income,
            "monthly_expenses_ngn": expenses,
            "existing_monthly_debt_ngn": debt,
            "requested_amount_ngn": amount,
            "term_months": term,
            "previous_loan_count": rng.integers(0, 9, rows),
            "previous_repayment_rate": rng.uniform(0, 1, rows),
            "previous_default_count": rng.integers(0, 4, rows),
            "disposable_income_ngn": income - expenses - debt,
            "estimated_monthly_repayment_ngn": amount / term,
            "repayment_to_income_ratio": (amount / term) / income,
            "days_past_due": rng.integers(0, 91, rows),
            "delinquency_within_90_days": rng.integers(0, 2, rows),
            "delinquent": np.tile([0, 1], rows // 2),
        }
    )

    return data


# ============================================================
# F2 METRIC
# ============================================================


def test_f2_weights_recall_more_than_precision():
    result = training.calculate_f2(
        precision=0.5,
        recall=0.8,
    )

    expected = (5 * 0.5 * 0.8) / (4 * 0.5 + 0.8)

    assert result == pytest.approx(expected)


def test_f2_returns_zero_when_both_metrics_are_zero():
    assert training.calculate_f2(0, 0) == 0.0


# ============================================================
# FEATURE DEFINITIONS AND TARGET LEAKAGE
# ============================================================


def test_feature_list_excludes_outcome_columns():
    outcome_columns = {
        "days_past_due",
        "delinquency_within_90_days",
        "delinquent",
    }

    assert not outcome_columns.intersection(training.INPUT_FEATURES)


def test_feature_list_contains_expected_features():
    assert len(training.INPUT_FEATURES) == 13

    assert training.CATEGORICAL_FEATURES == [
        "employment_type",
        "repayment_frequency",
    ]


# ============================================================
# MODEL CANDIDATES AND PREPROCESSING
# ============================================================


def test_build_candidates_returns_both_models():
    candidates = training.build_candidates()

    assert set(candidates) == {
        "loan-logreg-v2",
        "loan-rf-v2",
    }


def test_preprocessor_handles_unseen_categories():
    preprocessor = training.build_preprocessor(scale_numeric=True)

    data = make_dataset(20)

    preprocessor.fit(data[training.INPUT_FEATURES])

    unseen = data[training.INPUT_FEATURES].iloc[[0]].copy()
    unseen["employment_type"] = "NEW_EMPLOYMENT_TYPE"

    transformed = preprocessor.transform(unseen)

    assert transformed.shape[0] == 1


# ============================================================
# THRESHOLD OPTIMISATION
# ============================================================


def test_threshold_selection_prefers_precision_when_recall_target_met(
    monkeypatch,
):
    class FakeModel:
        def predict_proba(self, features):
            probabilities = features["probability"].to_numpy()

            return np.column_stack(
                [
                    1 - probabilities,
                    probabilities,
                ]
            )

    monkeypatch.setattr(
        training,
        "THRESHOLD_CANDIDATES",
        [0.2, 0.5, 0.8],
    )

    monkeypatch.setattr(
        training,
        "MINIMUM_TARGET_RECALL",
        0.5,
    )

    features = pd.DataFrame(
        {
            "probability": [
                0.9,
                0.85,
                0.7,
                0.6,
                0.4,
                0.3,
                0.2,
                0.1,
            ]
        }
    )

    target = pd.Series(
        [
            1,
            1,
            1,
            0,
            0,
            0,
            0,
            0,
        ]
    )

    _, selected = training.evaluate_thresholds(
        FakeModel(),
        features,
        target,
    )

    assert selected["recall"] >= 0.5
    assert selected["recall_target_achieved"] is True

    # Threshold 0.8 gives higher precision while
    # still satisfying the minimum recall requirement.
    assert selected["threshold"] == 0.8


def test_threshold_selection_falls_back_to_highest_f2(
    monkeypatch,
):
    class FakeModel:
        def predict_proba(self, features):
            probabilities = features["probability"].to_numpy()

            return np.column_stack(
                [
                    1 - probabilities,
                    probabilities,
                ]
            )

    monkeypatch.setattr(
        training,
        "THRESHOLD_CANDIDATES",
        [0.2, 0.5, 0.8],
    )

    monkeypatch.setattr(
        training,
        "MINIMUM_TARGET_RECALL",
        1.0,
    )

    features = pd.DataFrame(
        {
            "probability": [
                0.9,
                0.8,
                0.7,
                0.1,
                0.4,
                0.3,
                0.2,
                0.05,
            ]
        }
    )

    target = pd.Series(
        [
            1,
            1,
            1,
            1,
            0,
            0,
            0,
            0,
        ]
    )

    _, selected = training.evaluate_thresholds(
        FakeModel(),
        features,
        target,
    )

    # Even at the lowest threshold, one positive case
    # is missed. Therefore, 100% recall is impossible.
    assert selected["recall_target_achieved"] is False

    assert selected["selection_reason"].startswith("No threshold achieved")


# ============================================================
# DATASET VALIDATION
# ============================================================


def test_dataset_loader_accepts_valid_dataset(tmp_path):
    dataset = make_dataset(100)

    path = tmp_path / "dataset.csv"

    dataset.to_csv(
        path,
        index=False,
    )

    loaded = training.load_and_validate_dataset(path)

    assert len(loaded) == 100
    assert set(loaded["delinquent"].unique()) == {0, 1}


def test_dataset_loader_rejects_missing_required_columns(
    tmp_path,
):
    dataset = make_dataset(100).drop(columns=["monthly_income_ngn"])

    path = tmp_path / "dataset.csv"

    dataset.to_csv(
        path,
        index=False,
    )

    with pytest.raises(
        ValueError,
        match="missing required columns",
    ):
        training.load_and_validate_dataset(path)


def test_dataset_loader_rejects_missing_values(tmp_path):
    dataset = make_dataset(100)

    dataset.loc[0, "monthly_income_ngn"] = np.nan

    path = tmp_path / "dataset.csv"

    dataset.to_csv(
        path,
        index=False,
    )

    with pytest.raises(
        ValueError,
        match="missing values",
    ):
        training.load_and_validate_dataset(path)


def test_dataset_loader_rejects_duplicate_rows(tmp_path):
    dataset = make_dataset(100)

    dataset.iloc[1] = dataset.iloc[0]

    path = tmp_path / "dataset.csv"

    dataset.to_csv(
        path,
        index=False,
    )

    with pytest.raises(
        ValueError,
        match="duplicate rows",
    ):
        training.load_and_validate_dataset(path)


def test_dataset_loader_rejects_single_class_target(tmp_path):
    dataset = make_dataset(100)

    dataset["delinquent"] = 0

    path = tmp_path / "dataset.csv"

    dataset.to_csv(
        path,
        index=False,
    )

    with pytest.raises(
        ValueError,
        match="both binary classes",
    ):
        training.load_and_validate_dataset(path)
