"""Generate reproducible synthetic Nigerian microfinance loan data for V2.

This dataset is synthetic and must not be represented as actual Rubies MFB
customer or loan performance data.
"""

import numpy as np
import pandas as pd

from rubies_loan_model.schemas_v2 import FEATURE_SCHEMA_VERSION

DEFAULT_SAMPLE_SIZE = 10_000
DEFAULT_RANDOM_STATE = 42
DEFAULT_TARGET_PREVALENCE = 0.20

EMPLOYMENT_PROBABILITIES = {
    "SALARIED": 0.45,
    "SELF_EMPLOYED": 0.20,
    "BUSINESS_OWNER": 0.20,
    "UNEMPLOYED": 0.15,
}

REPAYMENT_PROBABILITIES = {
    "WEEKLY": 0.20,
    "BIWEEKLY": 0.20,
    "MONTHLY": 0.60,
}


def _sigmoid(values: np.ndarray) -> np.ndarray:
    """Convert risk scores into probabilities."""

    values = np.clip(values, -30, 30)
    return 1.0 / (1.0 + np.exp(-values))


def _calibrate_intercept(
    risk_scores: np.ndarray,
    target_prevalence: float,
) -> float:
    """Find an intercept that calibrates mean delinquency probability."""

    lower = -20.0
    upper = 20.0

    for _ in range(100):
        midpoint = (lower + upper) / 2

        mean_probability = _sigmoid(risk_scores + midpoint).mean()

        if mean_probability < target_prevalence:
            lower = midpoint
        else:
            upper = midpoint

    return (lower + upper) / 2


def generate_synthetic_dataset(
    n_samples: int = DEFAULT_SAMPLE_SIZE,
    random_state: int = DEFAULT_RANDOM_STATE,
    target_prevalence: float = DEFAULT_TARGET_PREVALENCE,
) -> pd.DataFrame:
    """Generate synthetic applicant features and 90-day delinquency outcomes.

    Target prevalence is a synthetic modelling assumption, not an observed
    portfolio default rate.

    Args:
        n_samples: Number of synthetic loan records.
        random_state: Random seed for reproducibility.
        target_prevalence: Expected mean delinquency probability.

    Returns:
        DataFrame containing applicant features and outcome columns.
    """

    if isinstance(n_samples, bool) or not isinstance(n_samples, int):
        raise ValueError("n_samples must be an integer.")

    if n_samples < 100:
        raise ValueError("n_samples must be at least 100.")

    if not 0 < target_prevalence < 1:
        raise ValueError("target_prevalence must be between 0 and 1.")

    rng = np.random.default_rng(random_state)

    # ---------------------------------------------------------
    # 1. Employment and repayment characteristics
    # ---------------------------------------------------------

    employment_type = rng.choice(
        list(EMPLOYMENT_PROBABILITIES),
        size=n_samples,
        p=list(EMPLOYMENT_PROBABILITIES.values()),
    )

    repayment_frequency = rng.choice(
        list(REPAYMENT_PROBABILITIES),
        size=n_samples,
        p=list(REPAYMENT_PROBABILITIES.values()),
    )

    # ---------------------------------------------------------
    # 2. Applicant financial characteristics
    # ---------------------------------------------------------

    # Log-uniform income distribution between ₦50,000 and ₦1.5m.
    monthly_income = np.exp(
        rng.uniform(
            np.log(50_000),
            np.log(1_500_000),
            size=n_samples,
        )
    )

    expense_ratio = rng.uniform(
        0.20,
        0.85,
        size=n_samples,
    )

    debt_ratio = rng.uniform(
        0.00,
        0.50,
        size=n_samples,
    )

    monthly_expenses = monthly_income * expense_ratio

    existing_monthly_debt = monthly_income * debt_ratio

    # Requested loan amount between ₦20,000 and ₦1m.
    requested_amount = np.exp(
        rng.uniform(
            np.log(20_000),
            np.log(1_000_000),
            size=n_samples,
        )
    )

    term_months = rng.integers(
        1,
        13,
        size=n_samples,
    )

    # ---------------------------------------------------------
    # 3. Previous borrowing and repayment history
    # ---------------------------------------------------------

    previous_loan_count = rng.integers(
        0,
        9,
        size=n_samples,
    )

    historical_default_probability = np.clip(
        0.08 + 0.20 * (expense_ratio > 0.65) + 0.15 * (debt_ratio > 0.30),
        0.05,
        0.60,
    )

    previous_default_count = np.minimum(
        rng.binomial(
            n=previous_loan_count,
            p=historical_default_probability,
        ),
        3,
    )

    # Applicants without previous loans have no repayment history.
    # We represent this as 1.0 (neutral/no recorded defaults).
    previous_repayment_rate = np.ones(n_samples)

    experienced_borrowers = previous_loan_count > 0

    historical_repayment_rate = 1.0 - (
        previous_default_count[experienced_borrowers] / previous_loan_count[experienced_borrowers]
    )

    repayment_noise = rng.uniform(
        0.85,
        1.00,
        size=experienced_borrowers.sum(),
    )

    previous_repayment_rate[experienced_borrowers] = np.clip(
        historical_repayment_rate * repayment_noise,
        0.0,
        1.0,
    )

    # ---------------------------------------------------------
    # 4. Derived financial features
    # ---------------------------------------------------------

    disposable_income = monthly_income - monthly_expenses - existing_monthly_debt

    # Principal-only monthly repayment estimate.
    # Interest, fees and frequency adjustments are excluded.
    estimated_monthly_repayment = requested_amount / term_months

    repayment_to_income_ratio = estimated_monthly_repayment / monthly_income

    disposable_income_ratio = disposable_income / monthly_income

    # ---------------------------------------------------------
    # 5. Synthetic delinquency risk score
    # ---------------------------------------------------------

    employment_risk = np.select(
        [
            employment_type == "UNEMPLOYED",
            employment_type == "SELF_EMPLOYED",
            employment_type == "BUSINESS_OWNER",
        ],
        [
            1.10,
            0.35,
            0.25,
        ],
        default=0.0,
    )

    risk_scores = (
        employment_risk
        + 2.0 * (repayment_to_income_ratio - 0.20)
        + 1.5
        * np.maximum(
            0.0,
            -disposable_income_ratio,
        )
        + 1.0 * debt_ratio
        + 0.80 * previous_default_count
        + 1.50 * (1.0 - previous_repayment_rate)
        + 0.20 * (term_months <= 3)
        + rng.normal(
            0.0,
            0.45,
            size=n_samples,
        )
    )

    # Calibrate average probability to the assumed prevalence.
    intercept = _calibrate_intercept(
        risk_scores,
        target_prevalence,
    )

    delinquency_probability = _sigmoid(risk_scores + intercept)

    # Sample outcomes probabilistically.
    delinquent = rng.binomial(
        1,
        delinquency_probability,
        size=n_samples,
    )

    # ---------------------------------------------------------
    # 6. Simulated days past due
    # ---------------------------------------------------------

    days_past_due = np.where(
        delinquent == 1,
        rng.integers(30, 91, size=n_samples),
        rng.integers(0, 30, size=n_samples),
    )

    # ---------------------------------------------------------
    # 7. Construct dataset
    # ---------------------------------------------------------

    data = pd.DataFrame(
        {
            "employment_type": employment_type,
            "monthly_income_ngn": (monthly_income.round(2)),
            "monthly_expenses_ngn": (monthly_expenses.round(2)),
            "existing_monthly_debt_ngn": (existing_monthly_debt.round(2)),
            "requested_amount_ngn": (requested_amount.round(2)),
            "term_months": term_months,
            "repayment_frequency": repayment_frequency,
            "previous_loan_count": previous_loan_count,
            "previous_repayment_rate": (previous_repayment_rate.round(4)),
            "previous_default_count": previous_default_count,
            "disposable_income_ngn": (disposable_income.round(2)),
            "estimated_monthly_repayment_ngn": (estimated_monthly_repayment.round(2)),
            "repayment_to_income_ratio": (repayment_to_income_ratio.round(6)),
            "days_past_due": days_past_due,
            "delinquency_within_90_days": delinquent,
            "delinquent": delinquent,
        }
    )

    # ---------------------------------------------------------
    # 8. Dataset metadata
    # ---------------------------------------------------------

    data.attrs["feature_schema_version"] = FEATURE_SCHEMA_VERSION

    data.attrs["synthetic_data"] = True

    data.attrs["random_state"] = random_state

    data.attrs["target_prevalence_assumption"] = target_prevalence

    data.attrs["observed_delinquency_prevalence"] = float(data["delinquent"].mean())

    data.attrs["employment_distribution_assumption"] = EMPLOYMENT_PROBABILITIES.copy()

    data.attrs["repayment_frequency_assumption"] = REPAYMENT_PROBABILITIES.copy()

    return data
