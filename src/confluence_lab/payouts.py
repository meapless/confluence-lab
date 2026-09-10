from __future__ import annotations

from enum import StrEnum


class TiePolicy(StrEnum):
    REFUND = "refund"
    LOSS = "loss"
    WIN = "win"


def _validate_payout(payout: float) -> None:
    if not 0 <= payout <= 10:
        raise ValueError("payout must be a decimal return, e.g. 0.82 for 82%")


def break_even_win_rate(payout: float) -> float:
    """Return the win probability required for zero expectancy."""
    _validate_payout(payout)
    return 1.0 / (1.0 + payout)


def settle_binary_trade(*, direction: int, entry_price: float, exit_price: float, payout: float, stake: float = 1.0, tie_policy: TiePolicy | str = TiePolicy.REFUND) -> tuple[str, float]:
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 (CALL) or -1 (PUT)")
    if stake <= 0:
        raise ValueError("stake must be positive")
    _validate_payout(payout)
    tie_policy = TiePolicy(tie_policy)
    signed_delta = direction * (exit_price - entry_price)
    if signed_delta > 0:
        return "win", stake * payout
    if signed_delta < 0:
        return "loss", -stake
    if tie_policy is TiePolicy.REFUND:
        return "tie", 0.0
    if tie_policy is TiePolicy.LOSS:
        return "loss", -stake
    return "win", stake * payout
