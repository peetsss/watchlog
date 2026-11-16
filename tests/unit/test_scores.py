from decimal import Decimal

from app.services.scores import round_score, score_decimal


def test_totals_round_half_up() -> None:
    assert round_score(8.25) == 8.3
    assert round_score(8.24) == 8.2
    assert round_score(Decimal("8.25")) == 8.3
    assert round_score(8.15) == 8.2
    assert round_score(None) is None


def test_individual_scores_round_half_up() -> None:
    assert score_decimal(8.25) == Decimal("8.3")
    assert score_decimal(8.0) == Decimal("8.0")
