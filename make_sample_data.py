"""
Generate sample cash data for a hypothetical bank branch.

Outputs two CSVs:
  daily_withdrawals.csv  - one row per day of customer withdrawals
  cash_orders.csv        - one row per cash order (lump sum meant to cover 7 days)

Assumptions (all made up, tweak freely):
  - Withdrawals happen every day (ATM + teller), lower on weekends.
  - Spikes on paydays (1st and 15th), before Thanksgiving, Christmas, New Year.
  - Orders are placed every Monday and delivered on Wednesday (2-day lead time).
  - Each order is meant to cover the 7 days starting on the delivery date.
  - Order amount = naive forecast: average of the last 4 weeks, same weekday,
    summed over the 7 coverage days, plus a 5% buffer, rounded up to $5,000.
    This forecast knows nothing about holidays, so it should miss around them.
"""
import numpy as np
import pandas as pd

BRANCH_ID = "DND4996"
START = pd.Timestamp("2025-11-01")
END = pd.Timestamp("2026-01-10")
WARMUP_START = START - pd.Timedelta(weeks=5)  # history the forecast needs
COVER_DAYS = 7
LEAD_DAYS = 2
ORDER_WEEKDAY = 0  # Monday
BUFFER = 0.05
ROUND_TO = 5_000
OPENING_BALANCE = 150_000

rng = np.random.default_rng(4996)

# ---------------------------------------------------------------- withdrawals
dates = pd.date_range(WARMUP_START, END, freq="D")

BASE = 22_000
weekday_factor = {0: 1.15, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.30, 5: 0.85, 6: 0.55}

# One-off multipliers for specific dates
events = {
    "2025-11-26": 1.35,  # day before Thanksgiving
    "2025-11-27": 0.40,  # Thanksgiving
    "2025-11-28": 1.25,  # Black Friday
    "2025-12-19": 1.30,
    "2025-12-20": 1.35,
    "2025-12-22": 1.45,
    "2025-12-23": 1.60,
    "2025-12-24": 1.40,
    "2025-12-25": 0.35,  # Christmas
    "2025-12-31": 1.40,
    "2026-01-01": 0.45,  # New Year's Day
}
events = {pd.Timestamp(k): v for k, v in events.items()}

amounts = []
for d in dates:
    m = weekday_factor[d.weekday()]
    if d.day in (1, 15):
        m *= 1.40  # payday
    elif d.day in (2, 16):
        m *= 1.15  # payday tail
    m *= events.get(d, 1.0)
    noise = rng.lognormal(mean=0.0, sigma=0.12)
    amounts.append(round(BASE * m * noise, -2))  # nearest $100

withdrawals = pd.DataFrame(
    {"branch_id": BRANCH_ID, "date": dates, "withdrawal_amount": amounts}
)

# --------------------------------------------------------------------- orders
w = withdrawals.set_index("date")["withdrawal_amount"]


def forecast_day(day, as_of):
    """Average of the same weekday over the 4 weeks before `as_of`."""
    hist = w[(w.index < as_of) & (w.index.weekday == day.weekday())]
    return hist.tail(4).mean()


order_dates = pd.date_range(START, END, freq="D")
order_dates = order_dates[order_dates.weekday == ORDER_WEEKDAY]

orders = []
for od in order_dates:
    receipt = od + pd.Timedelta(days=LEAD_DAYS)
    if receipt > END:
        break
    cover = pd.date_range(receipt, periods=COVER_DAYS, freq="D")
    fc = sum(forecast_day(d, od) for d in cover) * (1 + BUFFER)
    amount = int(np.ceil(fc / ROUND_TO) * ROUND_TO)
    orders.append(
        {
            "branch_id": BRANCH_ID,
            "order_date": od.date(),
            "receipt_date": receipt.date(),
            "coverage_start": cover[0].date(),
            "coverage_end": cover[-1].date(),
            "order_amount": amount,
        }
    )
orders = pd.DataFrame(orders)

# Drop the warm-up rows; keep Nov 1 - Jan 10 only
withdrawals = withdrawals[withdrawals["date"] >= START].reset_index(drop=True)
withdrawals["date"] = withdrawals["date"].dt.date

withdrawals.to_csv("daily_withdrawals.csv", index=False)
orders.to_csv("cash_orders.csv", index=False)

print(f"Opening balance on {START.date()}: ${OPENING_BALANCE:,}")
print(f"\n{len(withdrawals)} days of withdrawals")
print(withdrawals.head(10).to_string(index=False))
print(f"\n{len(orders)} orders")
print(orders.to_string(index=False))
