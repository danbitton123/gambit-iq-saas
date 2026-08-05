from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20260804
TODAY = pd.Timestamp("2026-08-04")
START = pd.Timestamp("2026-01-01")


def _ids(prefix: str, size: int, width: int = 6) -> np.ndarray:
    return np.array([f"{prefix}-{i:0{width}d}" for i in range(1, size + 1)])


def build_players(rng: np.random.Generator, n: int = 8_000) -> pd.DataFrame:
    registration = START + pd.to_timedelta(
        rng.integers(0, (TODAY - START).days + 1, n), unit="D"
    )
    countries = rng.choice(
        ["United Kingdom", "Canada", "Germany", "Spain", "Italy", "Sweden"],
        n,
        p=[.25, .19, .17, .15, .14, .10],
    )
    channels = rng.choice(
        ["Google", "Meta", "Organic", "Affiliate Alpha", "Affiliate Nova", "Influencers"],
        n,
        p=[.22, .18, .21, .17, .13, .09],
    )
    latent_value = rng.lognormal(4.15, .95, n)
    vip = pd.cut(
        latent_value,
        bins=[-np.inf, 45, 110, 260, np.inf],
        labels=["Standard", "Silver", "Gold", "Platinum"],
    ).astype(str)
    return pd.DataFrame(
        {
            "player_id": _ids("PLR", n),
            "registration_date": registration,
            "country": countries,
            "channel": channels,
            "device": rng.choice(["Mobile", "Desktop", "Tablet"], n, p=[.67, .28, .05]),
            "vip_level": vip,
            "kyc_status": rng.choice(["Verified", "Pending", "Rejected"], n, p=[.91, .07, .02]),
            "age_group": rng.choice(["18-24", "25-34", "35-44", "45-54", "55+"], n, p=[.09, .31, .29, .19, .12]),
            "latent_value": latent_value.round(2),
        }
    )


def build_games() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("G001", "Blackjack Live", "Blackjack", .990, "Evolution"),
            ("G002", "Roulette Live", "Roulette", .973, "Evolution"),
            ("G003", "Baccarat Live", "Baccarat", .988, "Pragmatic Play"),
            ("G004", "Three Card Poker", "Poker", .966, "Playtech"),
            ("G005", "Dragon Tiger", "Dragon Tiger", .963, "Pragmatic Play"),
            ("G006", "Casino Hold'em", "Poker", .978, "Playtech"),
        ],
        columns=["game_id", "game_name", "game_family", "theoretical_rtp", "provider"],
    )


def build_sessions(
    rng: np.random.Generator, players: pd.DataFrame, games: pd.DataFrame, n: int = 72_000
) -> pd.DataFrame:
    weights = np.power(players["latent_value"].to_numpy(), .38)
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
    vip_mult = pd.Series(players.iloc[pidx]["vip_level"]).map(
        {"Standard": 1.0, "Silver": 1.5, "Gold": 2.7, "Platinum": 6.0}
    ).to_numpy()
    bets = np.clip(rng.lognormal(5.05, .85, n) * vip_mult * (duration / 45) ** .55, 10, 500_000)
    rtp_lookup = games.set_index("game_id")["theoretical_rtp"].to_dict()
    theoretical = np.array([rtp_lookup[g] for g in game_id])
    session_noise = rng.normal(0, .115, n)
    payout = np.clip(bets * (theoretical + session_noise), 0, bets * 2.8)
    ggr = bets - payout
    return pd.DataFrame(
        {
            "session_id": _ids("SES", n, 7),
            "player_id": player_id,
            "game_id": game_id,
            "session_start": session_start,
            "duration_minutes": duration.round(1),
            "total_bet_amount": bets.round(2),
            "total_payout_amount": payout.round(2),
            "casino_ggr": ggr.round(2),
            "bet_count": np.maximum(1, (duration * rng.uniform(1.2, 3.8, n)).astype(int)),
        }
    )


def build_transactions(
    rng: np.random.Generator, players: pd.DataFrame, n: int = 31_000
) -> pd.DataFrame:
    weights = np.power(players["latent_value"].to_numpy(), .34)
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
    return pd.DataFrame(
        {
            "transaction_id": _ids("TRX", n, 7),
            "player_id": players.iloc[pidx]["player_id"].to_numpy(),
            "transaction_date": pd.to_datetime(dates) + pd.to_timedelta(rng.integers(0, 24 * 60, n), unit="m"),
            "transaction_type": tx_type,
            "amount": amounts.round(2),
            "transaction_status": status,
            "payment_method": method,
            "processing_fee": (amounts * fee_rate).round(2),
        }
    )


def build_sports_bets(rng: np.random.Generator, players: pd.DataFrame, n: int = 48_000) -> pd.DataFrame:
    pidx = rng.choice(len(players), n)
    dates = START + pd.to_timedelta(rng.integers(0, (TODAY - START).days + 1, n), unit="D")
    sport = rng.choice(["Football", "Basketball", "Tennis", "Esports"], n, p=[.50, .23, .18, .09])
    is_live = rng.random(n) < .31
    odds = np.clip(rng.lognormal(.58, .48, n), 1.05, 15)
    stake = np.clip(rng.lognormal(3.8, 1.0, n), 2, 50_000)
    win_prob = np.clip(.94 / odds, .03, .88)
    won = rng.random(n) < win_prob
    payout = np.where(won, stake * odds, 0)
    return pd.DataFrame(
        {
            "bet_id": _ids("BET", n, 7),
            "player_id": players.iloc[pidx]["player_id"].to_numpy(),
            "bet_date": dates + pd.to_timedelta(rng.integers(0, 24 * 60, n), unit="m"),
            "sport": sport,
            "is_live": is_live.astype(int),
            "odds": odds.round(2),
            "stake": stake.round(2),
            "payout": payout.round(2),
            "sportsbook_ggr": (stake - payout).round(2),
            "event_name": pd.Series(sport).map(
                {"Football": "Premier Match", "Basketball": "Pro League", "Tennis": "Open Championship", "Esports": "Masters Series"}
            ),
        }
    )


def build_model_scores(
    rng: np.random.Generator, players: pd.DataFrame, sessions: pd.DataFrame
) -> pd.DataFrame:
    activity = sessions.groupby("player_id").agg(
        session_count=("session_id", "count"),
        lifetime_ggr=("casino_ggr", "sum"),
        total_bets=("total_bet_amount", "sum"),
        last_session=("session_start", "max"),
        avg_duration=("duration_minutes", "mean"),
    ).reindex(players["player_id"]).fillna({"session_count": 0, "lifetime_ggr": 0, "total_bets": 0, "avg_duration": 0})
    recency = (TODAY - pd.to_datetime(activity["last_session"])).dt.days.fillna(220).clip(0, 220)
    frequency = activity["session_count"].to_numpy()
    value = np.maximum(activity["lifetime_ggr"].to_numpy(), 0)
    churn = 1 / (1 + np.exp(-(-2.0 + recency.to_numpy() / 18 - np.log1p(frequency) * .35)))
    churn = np.clip(churn + rng.normal(0, .05, len(players)), .01, .99)
    pred_ltv = np.clip(np.log1p(value) * 75 + players["latent_value"].to_numpy() * 1.5 + rng.normal(0, 45, len(players)), 10, 15_000)
    fraud = np.clip(rng.beta(1.2, 12, len(players)) + (players["kyc_status"].to_numpy() != "Verified") * .25, 0, .99)
    rg = np.clip(rng.beta(1.3, 15, len(players)) + (activity["avg_duration"].to_numpy() > 80) * .18 + (frequency > 25) * .12, 0, .99)
    action = np.select(
        [rg >= .55, fraud >= .55, (churn >= .7) & (pred_ltv >= 500), pred_ltv >= 1800],
        ["Player protection review", "Fraud review", "Retention review", "VIP review"],
        default="Monitor",
    )
    return pd.DataFrame(
        {
            "player_id": players["player_id"],
            "predicted_ltv_90d": pred_ltv.round(2),
            "churn_probability": churn.round(4),
            "fraud_risk": fraud.round(4),
            "rg_risk": rg.round(4),
            "recommended_action": action,
            "model_confidence": rng.uniform(.68, .97, len(players)).round(4),
            "last_session": pd.to_datetime(activity["last_session"]).to_numpy(),
            "session_count": frequency,
            "lifetime_ggr": activity["lifetime_ggr"].to_numpy().round(2),
        }
    )


def generate_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rng = np.random.default_rng(SEED)
    players = build_players(rng)
    games = build_games()
    sessions = build_sessions(rng, players, games)
    transactions = build_transactions(rng, players)
    sports_bets = build_sports_bets(rng, players)
    with sqlite3.connect(path) as conn:
        players.drop(columns="latent_value").to_sql("raw_players", conn, if_exists="replace", index=False)
        games.to_sql("raw_games", conn, if_exists="replace", index=False)
        sessions.to_sql("raw_sessions", conn, if_exists="replace", index=False)
        transactions.to_sql("raw_transactions", conn, if_exists="replace", index=False)
        sports_bets.to_sql("raw_sports_bets", conn, if_exists="replace", index=False)
        conn.executescript(
            """
            CREATE UNIQUE INDEX idx_raw_players_id ON raw_players(player_id);
            CREATE UNIQUE INDEX idx_raw_games_id ON raw_games(game_id);
            CREATE UNIQUE INDEX idx_raw_sessions_id ON raw_sessions(session_id);
            CREATE INDEX idx_raw_sessions_date ON raw_sessions(session_start);
            CREATE INDEX idx_raw_sessions_player ON raw_sessions(player_id);
            CREATE UNIQUE INDEX idx_raw_transactions_id ON raw_transactions(transaction_id);
            CREATE INDEX idx_raw_transactions_date ON raw_transactions(transaction_date);
            CREATE UNIQUE INDEX idx_raw_sports_id ON raw_sports_bets(bet_id);
            CREATE INDEX idx_raw_sports_date ON raw_sports_bets(bet_date);
            """
        )
    from data.warehouse import build_warehouse
    build_warehouse(path, include_ml=False)


if __name__ == "__main__":
    from config import DB_PATH
    from ml.pipeline import train_and_score

    generate_database(DB_PATH)
    report = train_and_score(DB_PATH)
    from data.warehouse import build_warehouse
    build_warehouse(DB_PATH, include_ml=True)
    print(f"Generated SQL warehouse and trained ML models: {DB_PATH}")
    print(report)
