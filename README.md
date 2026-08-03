# Option Terminal Paper Trading

Standalone professional paper-trading app using live FYERS market data and simulated orders only.

## Run

```bash
cd /Users/apple/Desktop/PaperTradingApp
python3 -m pip install -r requirements.txt
python3 -m streamlit run paper_app.py
```

The app creates twelve independent paper portfolios: four NIFTY slots, four BANKNIFTY slots, and four SENSEX slots. Slot 1 is always mapped to the nearest live expiry, Slot 2 to the next expiry, and so on; the mapping rolls automatically as expiries change. Orders and positions are stored in `data/paper_trading.db`; reports can be exported as CSV or Excel.

Configure FYERS credentials through the sidebar or `FYERS_*` environment variables. Paper orders never call a FYERS order endpoint.

## Supabase persistence

1. Run `paper_schema.sql` once in the Supabase SQL Editor.
2. Configure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in Streamlit secrets or environment variables.
3. Start the app normally. Supabase will restore and persist the paper portfolios, orders, fills, positions, and equity snapshots. If Supabase is unavailable, the app continues using its local SQLite fallback.
