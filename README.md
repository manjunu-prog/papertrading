# Option Terminal Paper Trading

Standalone professional paper-trading app using live FYERS market data and simulated orders only.

## Run

```bash
cd /Users/apple/Desktop/PaperTradingApp
python3 -m pip install -r requirements.txt
python3 -m streamlit run paper_app.py
```

The app creates twelve independent paper portfolios: four NIFTY slots, four BANKNIFTY slots, and four SENSEX slots. Orders and positions are stored in `data/paper_trading.db`; reports can be exported as CSV or Excel.

Configure FYERS credentials through the sidebar or `FYERS_*` environment variables. Paper orders never call a FYERS order endpoint.
