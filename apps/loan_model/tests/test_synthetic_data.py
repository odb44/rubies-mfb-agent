import pandas as pd
import pytest
from rubies_loan_model.synthetic_data import generate_synthetic_dataset


def test_generator_returns_expected_number_of_rows():
    data = generate_synthetic_dataset()

    assert len(data) == 10_000


def test_generator_is_reproducible():
    first = generate_synthetic_dataset(n_samples=500, random_state=42)
    second = generate_synthetic_dataset(n_samples=500, random_state=42)

    pd.testing.assert_frame_equal(first, second)


def test_generator_produces_expected_columns():
    data = generate_synthetic_dataset(n_samples=500)

    expected_columns = {
        "employment_type",
        "monthly_income_ngn",
        "monthly_expenses_ngn",
        "existing_monthly_debt_ngn",
        "requested_amount_ngn",
        "term_months",
        "repayment_frequency",
        "previous_loan_count",
        "previous_repayment_rate",
        "previous_default_count",
        "disposable_income_ngn",
        "estimated_monthly_repayment_ngn",
        "repayment_to_income_ratio",
        "days_past_due",
        "delinquency_within_90_days",
        "delinquent",
    }

    assert expected_columns.issubset(data.columns)


def test_numeric_features_stay_within_expected_ranges():
    data = generate_synthetic_dataset()

    assert data["monthly_income_ngn"].between(50_000, 1_500_000).all()
    assert data["requested_amount_ngn"].between(20_000, 1_000_000).all()
    assert data["term_months"].between(1, 12).all()
    assert data["previous_loan_count"].between(0, 8).all()
    assert data["previous_default_count"].between(0, 3).all()
    assert data["previous_repayment_rate"].between(0, 1).all()


def test_previous_defaults_never_exceed_previous_loans():
    data = generate_synthetic_dataset()

    assert (data["previous_default_count"] <= data["previous_loan_count"]).all()


def test_delinquency_target_matches_days_past_due():
    data = generate_synthetic_dataset()

    expected_target = (data["days_past_due"] >= 30).astype(int)

    pd.testing.assert_series_equal(
        data["delinquent"],
        expected_target,
        check_names=False,
    )


def test_delinquency_prevalence_is_approximately_twenty_percent():
    data = generate_synthetic_dataset()

    prevalence = data["delinquent"].mean()

    assert 0.17 <= prevalence <= 0.23


def test_invalid_sample_size_is_rejected():
    with pytest.raises(ValueError, match="n_samples"):
        generate_synthetic_dataset(n_samples=50)


def test_invalid_target_prevalence_is_rejected():
    with pytest.raises(ValueError, match="target_prevalence"):
        generate_synthetic_dataset(target_prevalence=1.0)
