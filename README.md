# Kraken Arbitrage Bot

Scans Kraken for loop arbitrage — sequences of trades that start and end in USD and
come back with more than they started with, after fees — and can execute them.

Example loop: `USD → ADA → EUR → USD`. Buy ADA with dollars, sell it for euros,
convert the euros back to dollars. If ADA is priced slightly differently in USD and
EUR, the round trip can end above the starting amount.

> **Mock mode is on by default.** The bot logs what it would trade without placing
> orders. Live execution is untested against the real API. Read [Risks](#risks)
> before turning it off.

## How it works

Each cycle (every 5 seconds by default):

1. **Screen** – one `/Ticker` request fetches the best bid/ask for every pair. Every
   loop is priced at top of book, net of fees. Top of book is the best price at any
   size, so a loop that loses here loses at every size.
2. **Verify** – the few loops that pass are re-priced against the full order books,
   walking down each level at a real trade size.
3. **Size** – with auto-sizing on, it finds the trade size (up to a cap) that makes
   the most dollars, since deeper book levels eventually eat the edge.
4. **Trade** – executes the first verified loop as IOC limit orders, one leg at a
   time, or just logs it in mock mode.

Loops are built once at startup from Kraken's pair list; each cycle only re-prices them.

## Setup

Requires Python 3.9+.

```bash
git clone https://github.com/<you>/kraken-arb-bot.git
cd kraken-arb-bot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### API key (optional for mock mode)

Without a key the bot still runs in mock mode, using a fallback fee rate.
With a key it reads your real fee tier and, in live mode, your balance.

1. Create an API key in Kraken (Settings → API).
2. Grant only what the bot needs: query funds, query open/closed orders,
   create & modify orders, cancel orders. **Do not grant withdrawal permission.**
3. Copy `kraken.key.example` to `kraken.key` and put the API key on line 1 and
   the private key on line 2.

`kraken.key` is in `.gitignore` and will not be committed.

### Run

```bash
python arb_bot.py
```

Stop with `Ctrl+C`.

## Configuration

All settings are in the `Config` class at the top of `arb_bot.py`.

| Setting | Default | What it does |
|---|---|---|
| `SCAN_MODE` | `'usd_eur'` | `'usd_eur'`: only USD/EUR-quoted pairs, 3-trade loops through EUR. `'all'`: every pair between listed assets (cross pairs like AAVE/ETH). |
| `MAX_PATH_LEGS` | `3` | Longest loop in `'all'` mode. 4 finds more loops but each pays a fourth fee. |
| `MANUAL_KRAKEN_BASES` | ~500 assets | Assets to consider. Uses Kraken's codes (`XXBT` = Bitcoin, `ZUSD` = USD). |
| `PROFIT_THRESHOLD` | `0.05` | Minimum net profit in USD to trade. |
| `AUTO_SIZE` | `True` | Trade the most profitable size the books support. |
| `MAX_TRADE_CAPITAL` | `10000` | Cap for auto-sizing. Live mode also caps at 99% of your free USD. |
| `TRADE_CAPITAL` | `1000` | Fixed size when `AUTO_SIZE = False`. |
| `SLIPPAGE_TOLERANCE_PERCENT` | `0.05` | Extra room on each limit price. |
| `MOCK_EXECUTION` | `True` | `False` places real orders. |
| `POLL_INTERVAL` | `5` | Seconds between cycles. |
| `FALLBACK_TAKER_FEE_PERCENT` | `0.40` | Fee used if your real tier can't be read. |
| `ANALYZE_CAPACITY` | `True` | Log the profitable size range for each verified loop. |

## Output files

| File | Contents |
|---|---|
| `arb_bot.log` | One line per cycle, verification results, trades. |
| `arb_audit.log` | Per-leg detail of every verification: amounts, worst price, fee. |
| `arb_coverage.txt` | Written at startup: which listed assets are scanned, have no loop, or weren't found. |

### Reading the log

```
[cycle 12] Priced 744/744 loops. No opportunities. Closest: ZUSD -> AAVE -> XETH -> ZUSD multiplier 0.98958 (edge -1.042%)
```

The **multiplier** is what $1 becomes after the full loop, net of fees. `1.0` is
break-even. `0.98958` means $1,000 would come back as $989.58. The bot only
verifies loops above `1.0`.

## Risks

- **Fees usually exceed the gaps.** Each loop pays three taker fees. At Kraken's
  entry tiers that is roughly 1% or more per round trip; most price gaps are smaller.
  Expect long stretches with no opportunities.
- **Legs are not atomic.** Trades execute one after another. If a later leg fails or
  partially fills, you hold an intermediate asset. The bot halts trading and logs
  what you may be holding; it does not sell automatically.
- **Prices move.** Opportunities seen in a snapshot can be gone by the time orders
  land. Faster bots compete for the same gaps.
- **Untested live path.** Order placement has not been run against the real API.
  Test with a very small `MAX_TRADE_CAPITAL` first.

This is not financial advice. Use at your own risk.
