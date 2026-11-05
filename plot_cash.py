"""
Plot whether lump-sum cash orders cover daily withdrawals.

Reads daily_withdrawals.csv and cash_orders.csv (from make_sample_data.py)
and draws three panels:
  1. Cumulative cash received (steps) vs cumulative withdrawals
  2. End-of-day cash on hand (the sawtooth), with a safety-stock line
  3. Per-order scorecard: ordered minus actual withdrawals in its window
"""
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

OPENING_BALANCE = 150_000
SAFETY_STOCK = 60_000  # the level the branch never wants to drop below

# Palette (light mode)
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e6e5e0"
DEMAND = "#2a78d6"  # blue: withdrawals
SUPPLY = "#eb6834"  # orange: cash received / ordered
CRITICAL = "#d03b3b"  # status: shortfall
NEUTRAL = "#8a8984"

# ---------------------------------------------------------------- load data
w = pd.read_csv("daily_withdrawals.csv", parse_dates=["date"])
o = pd.read_csv(
    "cash_orders.csv",
    parse_dates=["order_date", "receipt_date", "coverage_start", "coverage_end"],
)
branch = w["branch_id"].iloc[0]

# One row per day: withdrawals, cash received that day, running totals
daily = w.set_index("date")[["withdrawal_amount"]].copy()
received = o.groupby("receipt_date")["order_amount"].sum()
daily["received"] = received.reindex(daily.index, fill_value=0)
daily["cum_withdrawn"] = daily["withdrawal_amount"].cumsum()
daily["cum_received"] = OPENING_BALANCE + daily["received"].cumsum()
daily["balance"] = daily["cum_received"] - daily["cum_withdrawn"]

# Per-order scorecard: actual withdrawals inside each coverage window
last_day = daily.index.max()


def actual_in_window(r):
    return daily.loc[r.coverage_start : r.coverage_end, "withdrawal_amount"].sum()


o["actual"] = o.apply(actual_in_window, axis=1)
o["complete"] = o["coverage_end"] <= last_day  # window fully inside the data
o["gap"] = o["order_amount"] - o["actual"]

# ------------------------------------------------------------------ styling
plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_2,
        "axes.titlecolor": TEXT,
        "axes.titleweight": "bold",
        "axes.titlesize": 12,
        "axes.titlelocation": "left",
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": TEXT_2,
        "ytick.color": TEXT_2,
        "font.size": 10,
        "legend.frameon": False,
    }
)
dollars = mticker.FuncFormatter(lambda v, _: f"${v / 1000:,.0f}k")

fig, (ax1, ax2, ax3) = plt.subplots(
    3, 1, figsize=(12, 13), gridspec_kw={"height_ratios": [1.2, 1, 1]}
)
fig.suptitle(
    f"Branch {branch}: do weekly cash orders cover daily withdrawals?",
    x=0.06, ha="left", fontsize=15, fontweight="bold", color=TEXT,
)

# Shade the holiday period on the two time-series panels
for ax in (ax1, ax2):
    ax.axvspan(pd.Timestamp("2025-12-19"), pd.Timestamp("2026-01-01"),
               color=GRID, alpha=0.6, lw=0, zorder=0)

# ---- Panel 1: cumulative supply vs demand
ax1.step(daily.index, daily["cum_received"], where="post",
         color=SUPPLY, lw=2, label="Cumulative cash received (incl. opening balance)")
ax1.plot(daily.index, daily["cum_withdrawn"],
         color=DEMAND, lw=2, label="Cumulative withdrawals")
ax1.fill_between(daily.index, daily["cum_withdrawn"], daily["cum_received"],
                 step="post", color=SUPPLY, alpha=0.08, lw=0)
ax1.set_title("1. Supply vs demand: the gap between the lines is cash on hand")
ax1.yaxis.set_major_formatter(dollars)
ax1.legend(loc="upper left")
ax1.text(pd.Timestamp("2025-12-25"), ax1.get_ylim()[1], "holidays",
         ha="center", va="top", color=TEXT_2, fontsize=9)

# ---- Panel 2: end-of-day cash on hand (sawtooth)
ax2.step(daily.index, daily["balance"], where="post", color=TEXT, lw=2,
         label="End-of-day cash on hand")
ax2.axhline(SAFETY_STOCK, color=CRITICAL, lw=1.2, ls="--")
ax2.text(daily.index[-1], SAFETY_STOCK, f"safety stock ${SAFETY_STOCK / 1000:.0f}k ",
         ha="right", va="bottom", color=CRITICAL, fontsize=9)
below = daily["balance"] < SAFETY_STOCK
ax2.fill_between(daily.index, daily["balance"], SAFETY_STOCK, where=below,
                 step="post", color=CRITICAL, alpha=0.25, lw=0)
# Mark each delivery
for d in o["receipt_date"]:
    if d in daily.index:
        ax2.plot(d, daily.loc[d, "balance"], "v", color=SUPPLY, ms=8, zorder=3)
ax2.plot([], [], "v", color=SUPPLY, ms=8, label="Cash delivery")
# Label the lowest point
low_day = daily["balance"].idxmin()
low = daily.loc[low_day, "balance"]
ax2.annotate(f"lowest: ${low / 1000:,.0f}k\n{low_day:%b %d}",
             (low_day, low), xytext=(0, -38), textcoords="offset points",
             ha="center", color=TEXT, fontsize=9,
             arrowprops=dict(arrowstyle="-", color=TEXT_2, lw=0.8))
ax2.set_ylim(bottom=min(0, low - 40_000))
ax2.set_title("2. Cash on hand: troughs just before each delivery show how close it got")
ax2.yaxis.set_major_formatter(dollars)
ax2.legend(loc="upper left")

for ax in (ax1, ax2):
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_xlim(daily.index[0], daily.index[-1])

# ---- Panel 3: per-order scorecard
labels = [f"{s:%b %d}–{e:%b %d}" for s, e in zip(o["coverage_start"], o["coverage_end"])]
colors = [NEUTRAL if not c else (CRITICAL if g < 0 else SUPPLY)
          for g, c in zip(o["gap"], o["complete"])]
bars = ax3.bar(labels, o["gap"], color=colors, width=0.7)
for b, c in zip(bars, o["complete"]):
    if not c:
        b.set_hatch("///")
        b.set_edgecolor(SURFACE)
ax3.axhline(0, color=TEXT_2, lw=1)
ax3.set_axisbelow(True)
for b, g, r, c in zip(bars, o["gap"], o["order_amount"] / o["actual"], o["complete"]):
    txt = f"{'+' if g >= 0 else '−'}${abs(g) / 1000:.0f}k\n({r:.2f}×)"
    if not c:
        txt += "\npartial"
    ax3.annotate(txt, (b.get_x() + b.get_width() / 2, g),
                 xytext=(0, 4 if g >= 0 else -4), textcoords="offset points",
                 ha="center", va="bottom" if g >= 0 else "top",
                 color=TEXT, fontsize=8.5)
ax3.set_title("3. Each order vs actual withdrawals in its 7-day window (ordered − actual)")
ax3.set_xlabel("Coverage window")
ax3.yaxis.set_major_formatter(dollars)
ax3.tick_params(axis="x", rotation=30)
ax3.margins(y=0.25)
ax3.legend(
    handles=[
        plt.Rectangle((0, 0), 1, 1, color=SUPPLY),
        plt.Rectangle((0, 0), 1, 1, color=CRITICAL),
        plt.Rectangle((0, 0), 1, 1, facecolor=NEUTRAL, hatch="///", edgecolor=SURFACE),
    ],
    labels=["Over-ordered (surplus)", "Under-ordered (shortfall)",
            "Window runs past end of data"],
    loc="upper left",
)

fig.tight_layout(rect=(0, 0, 1, 0.97), h_pad=2.5)
fig.savefig("cash_coverage.png", dpi=150)
print("Saved cash_coverage.png")
print(f"Lowest balance: ${low:,.0f} on {low_day:%Y-%m-%d}")
print(f"Days below safety stock: {below.sum()}")
