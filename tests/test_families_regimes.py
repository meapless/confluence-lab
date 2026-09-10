import pandas as pd

from confluence_lab.families import FAMILIES, get_strategy_family
from confluence_lab.matrix_cli import build_parser
from confluence_lab.regimes import (
    MarketRegime,
    classify_market_regime,
    classify_regime_from_features,
)
from confluence_lab.synthetic import generate_synthetic_ohlc


def test_strategy_family_grid_sizes_are_explicit_and_stable():
    assert get_strategy_family("trend_pullback").grid_size == 288
    assert get_strategy_family("range_reversion").grid_size == 288
    assert get_strategy_family("breakout").grid_size == 192
    assert sum(family.grid_size for family in FAMILIES.values()) == 768


def test_matrix_cli_exposes_all_strategy_families():
    parser = build_parser()
    for family in FAMILIES:
        args = parser.parse_args(["data.csv", "--family", family])
        assert args.family == family


def test_regime_classifier_labels_explainable_cases():
    rows = 25
    features = pd.DataFrame(
        {
            "close": [0.5] * rows,
            "high": [1.0] * rows,
            "low": [0.0] * rows,
            "ema_20": [0.6] * rows,
            "ema_50": [0.5] * rows,
            "ema_50_slope": [0.01] * rows,
            "adx_14": [30.0] * rows,
            "atr_percentile_100": [0.5] * rows,
            "candle_body_ratio": [0.4] * rows,
        }
    )

    labels = classify_regime_from_features(features)
    assert labels.iloc[22] == MarketRegime.STRONG_UPTREND.value

    features.loc[23, "adx_14"] = 10.0
    features.loc[23, "atr_percentile_100"] = 0.2
    labels = classify_regime_from_features(features)
    assert labels.iloc[23] == MarketRegime.QUIET_RANGE.value

    features.loc[24, "close"] = 1.1
    features.loc[24, "high"] = 1.2
    features.loc[24, "atr_percentile_100"] = 0.8
    features.loc[24, "candle_body_ratio"] = 0.8
    labels = classify_regime_from_features(features)
    assert labels.iloc[24] == MarketRegime.BREAKOUT_CANDIDATE.value


def test_regime_classifier_does_not_change_past_when_future_changes():
    frame = generate_synthetic_ohlc(rows=400, seed=73)
    original = classify_market_regime(frame)

    altered = frame.copy()
    altered.loc[300:, "close"] *= 3.0
    altered.loc[300:, "high"] = altered.loc[300:, ["open", "close"]].max(axis=1) + 0.01
    altered.loc[300:, "low"] = altered.loc[300:, ["open", "close"]].min(axis=1) - 0.01
    changed = classify_market_regime(altered)

    pd.testing.assert_series_equal(original.iloc[:300], changed.iloc[:300])
