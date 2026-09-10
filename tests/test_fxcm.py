import gzip

import pandas as pd
import pytest

from confluence_lab.fxcm import fxcm_week_url, normalize_fxcm_week


def _payload() -> bytes:
    csv = (
        "DateTime,BidOpen,BidHigh,BidLow,BidClose,AskOpen,AskHigh,AskLow,AskClose,TickQty\n"
        "2020-01-06 00:00:00,1.1000,1.1004,1.0998,1.1002,1.1002,1.1006,1.1000,1.1004,100\n"
        "2020-01-06 00:01:00,1.1002,1.1005,1.1001,1.1003,1.1004,1.1007,1.1003,1.1005,120\n"
    ).encode()
    return gzip.compress(csv)


def test_fxcm_week_url():
    assert fxcm_week_url("EUR/USD", 2020, 1) == (
        "https://candledata.fxcorporate.com/m1/EURUSD/2020/1.csv.gz"
    )


def test_fxcm_mid_normalization_retains_spread():
    frame = normalize_fxcm_week(_payload(), price_side="mid")
    assert len(frame) == 2
    assert frame.iloc[0]["open"] == pytest.approx(1.1001)
    assert frame.iloc[0]["high"] == pytest.approx(1.1005)
    assert frame.iloc[0]["low"] == pytest.approx(1.0999)
    assert frame.iloc[0]["close"] == pytest.approx(1.1003)
    assert frame.iloc[0]["spread_open"] == pytest.approx(0.0002)
    assert frame.iloc[0]["spread_close"] == pytest.approx(0.0002)
    assert frame.iloc[0]["volume"] == pytest.approx(100)
    assert frame.iloc[0]["timestamp"] == pd.Timestamp("2020-01-06T00:00:00Z")


def test_fxcm_bid_and_ask_sides_are_explicit():
    bid = normalize_fxcm_week(_payload(), price_side="bid")
    ask = normalize_fxcm_week(_payload(), price_side="ask")
    assert bid.iloc[1]["close"] == pytest.approx(1.1003)
    assert ask.iloc[1]["close"] == pytest.approx(1.1005)
