from confluence_lab.benchmark import benchmark_strategies
from confluence_lab.synthetic import generate_synthetic_ohlc


def main() -> None:
    frame = generate_synthetic_ohlc(rows=20_000, seed=42)
    report = benchmark_strategies(frame, expiry_bars=3, payout_column="payout")
    columns = ["split", "strategy", "trades", "win_rate", "expectancy", "total_pnl", "max_drawdown"]
    print("DEMO / SYNTHETIC DATA ONLY - NOT LIVE MARKET RESULTS")
    print(report[columns].to_string(index=False))


if __name__ == "__main__":
    main()
