"""Generate a synthetic 8-month operator export as CSV files, for testing Data Import Studio
with realistic multi-file data end to end (players, games, casino sessions, sportsbook bets,
transactions) instead of the packaged single-database demo.

Reuses the same distributions as data/generator.py (the packaged demo), but ending on the
ML pipeline's SCORING_CUTOFF so a real train_and_score() run succeeds on the imported data,
not just placeholder "Missing data" scores.

Usage: python -m tools.generate_sample_csvs [output_dir]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ml.shared.config import SCORING_CUTOFF

SEED = 20260804081
TODAY = pd.Timestamp(SCORING_CUTOFF)
START = TODAY - pd.DateOffset(months=8)


def _ids(prefix: str, size: int, width: int = 6) -> np.ndarray:
    return np.array([f"{prefix}-{i:0{width}d}" for i in range(1, size + 1)])


def build_players(rng: np.random.Generator, n: int = 8_000) -> pd.DataFrame:
    registration = START + pd.to_timedelta(rng.integers(0, (TODAY - START).days + 1, n), unit="D")
    countries = rng.choice(["United Kingdom", "Canada", "Germany", "Spain", "Italy", "Sweden"], n, p=[.25, .19, .17, .15, .14, .10])
    channels = rng.choice(["Google", "Meta", "Organic", "Affiliate Alpha", "Affiliate Nova", "Influencers"], n, p=[.22, .18, .21, .17, .13, .09])
    latent_value = rng.lognormal(4.15, .95, n)
    vip = pd.cut(latent_value, bins=[-np.inf, 45, 110, 260, np.inf], labels=["Standard", "Silver", "Gold", "Platinum"]).astype(str)
    frame = pd.DataFrame({
        "player_id": _ids("PLR", n), "registration_date": registration, "country": countries, "channel": channels,
        "device": rng.choice(["Mobile", "Desktop", "Tablet"], n, p=[.67, .28, .05]), "vip_level": vip,
        "kyc_status": rng.choice(["Verified", "Pending", "Rejected"], n, p=[.91, .07, .02]),
        "age_group": rng.choice(["18-24", "25-34", "35-44", "45-54", "55+"], n, p=[.09, .31, .29, .19, .12]),
    })
    frame["_latent_value"] = latent_value.round(2)
    return frame


def build_games() -> pd.DataFrame:
    return pd.DataFrame([
        ("G001", "Blackjack Live", "Blackjack", .990, "Evolution"),
        ("G002", "Roulette Live", "Roulette", .973, "Evolution"),
        ("G003", "Baccarat Live", "Baccarat", .988, "Pragmatic Play"),
        ("G004", "Three Card Poker", "Poker", .966, "Playtech"),
        ("G005", "Dragon Tiger", "Dragon Tiger", .963, "Pragmatic Play"),
        ("G006", "Casino Hold'em", "Poker", .978, "Playtech"),
    ], columns=["game_id", "game_name", "game_family", "theoretical_rtp", "provider"])


def build_sessions(rng: np.random.Generator, players: pd.DataFrame, games: pd.DataFrame, n: int = 80_000) -> pd.DataFrame:
    weights = np.power(players["_latent_value"].to_numpy(), .38)
    pidx = rng.choice(len(players), n, p=weights / weights.sum())
    player_id = players.iloc[pidx]["player_id"].to_numpy()
    reg = players.iloc[pidx]["registration_date"].to_numpy(dtype="datetime64[D]")
    end = np.datetime64(TODAY.date())
    available = (end - reg).astype("timedelta64[D]").astype(int) + 1
    offsets = (rng.random(n) * available).astype(int)
    session_date = reg + offsets.astype("timedelta64[D]")
    hour_weights = np.array([2, 1.5, 1, 1, 1, 1, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4, 4.5, 5, 6, 7, 8, 9, 10, 9, 6, 4], dtype=float)
    hours = rng.choice(np.arange(24), n, p=hour_weights / hour_weights.sum())
    minutes = rng.integers(0, 60, n)
    session_start = pd.to_datetime(session_date) + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m")
    game_id = rng.choice(games["game_id"], n, p=[.25, .28, .17, .12, .08, .10])
    duration = np.clip(rng.gamma(2.4, 18, n), 5, 240)
    vip_mult = pd.Series(players.iloc[pidx]["vip_level"]).map({"Standard": 1.0, "Silver": 1.5, "Gold": 2.7, "Platinum": 6.0}).to_numpy()
    bets = np.clip(rng.lognormal(5.05, .85, n) * vip_mult * (duration / 45) ** .55, 10, 500_000)
    rtp_lookup = games.set_index("game_id")["theoretical_rtp"].to_dict()
    theoretical = np.array([rtp_lookup[g] for g in game_id])
    session_noise = rng.normal(0, .115, n)
    payout = np.clip(bets * (theoretical + session_noise), 0, bets * 2.8)
    ggr = bets - payout
    return pd.DataFrame({
        "session_id": _ids("SES", n, 7), "player_id": player_id, "game_id": game_id, "session_start": session_start,
        "duration_minutes": duration.round(1), "total_bet_amount": bets.round(2), "total_payout_amount": payout.round(2),
        "casino_ggr": ggr.round(2), "bet_count": np.maximum(1, (duration * rng.uniform(1.2, 3.8, n)).astype(int)),
    })


def build_transactions(rng: np.random.Generator, players: pd.DataFrame, n: int = 34_000) -> pd.DataFrame:
    weights = np.power(players["_latent_value"].to_numpy(), .34)
    pidx = rng.choice(len(players), n, p=weights / weights.sum())
    reg = players.iloc[pidx]["registration_date"].to_numpy(dtype="datetime64[D]")
    end = np.datetime64(TODAY.date())
    available = (end - reg).astype("timedelta64[D]").astype(int) + 1
    dates = reg + (rng.random(n) * available).astype(int).astype("timedelta64[D]")
    tx_type = rng.choice(["Deposit", "Withdrawal"], n, p=[.64, .36])
    base = rng.lognormal(4.65, .9, n)
    amounts = base * np.where(tx_type == "Deposit", 1, 1.28)
    status = rng.choice(["Approved", "Declined", "Pending"], n, p=[.92, .055, .025])
    method = rng.choice(["Visa", "Mastercard", "Bank Transfer", "Apple Pay"], n, p=[.42, .30, .18, .10])
    fee_rate = pd.Series(method).map({"Visa": .0145, "Mastercard": .0155, "Bank Transfer": .0065, "Apple Pay": .009}).to_numpy()
    return pd.DataFrame({
        "transaction_id": _ids("TRX", n, 7), "player_id": players.iloc[pidx]["player_id"].to_numpy(),
        "transaction_date": pd.to_datetime(dates) + pd.to_timedelta(rng.integers(0, 24 * 60, n), unit="m"),
        "transaction_type": tx_type, "amount": amounts.round(2), "transaction_status": status,
        "payment_method": method, "processing_fee": (amounts * fee_rate).round(2),
    })


def build_sports_bets(rng: np.random.Generator, players: pd.DataFrame, n: int = 53_000) -> pd.DataFrame:
    pidx = rng.choice(len(players), n)
    dates = START + pd.to_timedelta(rng.integers(0, (TODAY - START).days + 1, n), unit="D")
    sport = rng.choice(["Football", "Basketball", "Tennis", "Esports"], n, p=[.50, .23, .18, .09])
    is_live = rng.random(n) < .31
    odds = np.clip(rng.lognormal(.58, .48, n), 1.05, 15)
    stake = np.clip(rng.lognormal(3.8, 1.0, n), 2, 50_000)
    win_prob = np.clip(.94 / odds, .03, .88)
    won = rng.random(n) < win_prob
    payout = np.where(won, stake * odds, 0)
    return pd.DataFrame({
        "bet_id": _ids("BET", n, 7), "player_id": players.iloc[pidx]["player_id"].to_numpy(),
        "bet_date": dates + pd.to_timedelta(rng.integers(0, 24 * 60, n), unit="m"), "sport": sport,
        "is_live": is_live.astype(int), "odds": odds.round(2), "stake": stake.round(2), "payout": payout.round(2),
        "sportsbook_ggr": (stake - payout).round(2),
        "event_name": pd.Series(sport).map({"Football": "Premier Match", "Basketball": "Pro League", "Tennis": "Open Championship", "Esports": "Masters Series"}),
    })


def generate(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    players = build_players(rng)
    games = build_games()
    sessions = build_sessions(rng, players, games)
    transactions = build_transactions(rng, players)
    sports_bets = build_sports_bets(rng, players)

    paths = {}
    for name, frame in (
        ("players", players.drop(columns="_latent_value")),
        ("games", games),
        ("casino_sessions", sessions),
        ("transactions", transactions),
        ("sportsbook_bets", sports_bets),
    ):
        path = output_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path
    return paths


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_export")
    written = generate(target)
    print(f"8-month synthetic export ({START.date()} → {TODAY.date()}) written to {target}/")
    for name, path in written.items():
        print(f"  {path}")
