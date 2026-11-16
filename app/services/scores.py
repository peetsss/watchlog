from decimal import ROUND_HALF_UP, Decimal

_SCORE_QUANTUM = Decimal("0.1")


def score_decimal(value: float) -> Decimal:
    return Decimal(str(value)).quantize(_SCORE_QUANTUM, rounding=ROUND_HALF_UP)


def round_score(value: float | Decimal | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(_SCORE_QUANTUM, rounding=ROUND_HALF_UP))
