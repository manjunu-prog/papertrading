"""Streamlit UI for the isolated 12-portfolio paper-trading workspace."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from api.option_chain import OptionChain
from config import INDEX_CONFIG
from paper_trading import PaperTradingStore


def _money(value) -> str:
    return f"₹{float(value or 0):,.2f}"


def _quote_symbols(store: PaperTradingStore, portfolio_id: str, selected_symbol: str = "") -> list[str]:
    symbols = {selected_symbol} if selected_symbol else set()
    positions = store.positions(portfolio_id)
    if not positions.empty:
        symbols.update(positions["symbol"].tolist())
    return sorted(symbols)


def _portfolio_selector(store: PaperTradingStore) -> tuple[pd.DataFrame, str]:
    portfolios = store.portfolios()
    labels = {row.id: f"{row.instrument} · {row.name}" for row in portfolios.itertuples()}
    selected = st.selectbox("Active portfolio", list(labels), format_func=labels.get, key="paper_portfolio")
    return portfolios, selected


def _inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root { --ink:#e8eef6; --muted:#8b98a9; --line:#273342; --panel:#121923; --panel2:#182230; --accent:#ff5b5f; --green:#30d39a; }
        [data-testid="stAppViewContainer"] { background: #0a0f15; }
        [data-testid="stHeader"] { background: rgba(10,15,21,.82); }
        [data-testid="stSidebar"] { background:#0d141c; border-right:1px solid #202b38; }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color:var(--ink); }
        .block-container { max-width:1500px; padding-top:2.1rem; padding-bottom:3rem; }
        h1,h2,h3 { letter-spacing:-.025em; }
        h1 { font-size:2.05rem !important; margin-bottom:.15rem !important; }
        h2 { font-size:1.25rem !important; margin-top:1.3rem !important; }
        h3 { font-size:1rem !important; }
        [data-testid="stMetric"] { background:linear-gradient(145deg,#151e29,#101720); border:1px solid var(--line); border-radius:14px; padding:14px 16px; min-height:96px; }
        [data-testid="stMetricLabel"] { color:var(--muted); font-size:.76rem; text-transform:uppercase; letter-spacing:.08em; }
        [data-testid="stMetricValue"] { color:var(--ink); font-size:1.38rem; }
        [data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--line) !important; border-radius:16px !important; background:rgba(18,25,35,.74); }
        div[data-testid="stForm"] { border:1px solid #344253; border-radius:16px; padding:1.1rem 1.2rem .8rem; background:linear-gradient(145deg,#151f2c,#101720); }
        div[data-testid="stForm"] label { color:#aeb9c8; font-size:.78rem; }
        .stButton button, .stDownloadButton button { border-radius:9px; border:1px solid #354354; }
        button[kind="primary"] { background:var(--accent) !important; border-color:var(--accent) !important; }
        button[kind="primary"] p { color:white !important; font-weight:700; }
        [data-testid="stTabs"] button { color:#8e9aaa; font-weight:600; }
        [data-testid="stTabs"] button[aria-selected="true"] { color:#ff6d70; border-bottom-color:#ff5b5f; }
        [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
        .paper-hero { display:flex; align-items:flex-start; justify-content:space-between; gap:20px; margin-bottom:1.15rem; }
        .paper-kicker { color:#ff6b6e; font-size:.72rem; letter-spacing:.16em; text-transform:uppercase; font-weight:800; margin-bottom:.35rem; }
        .paper-title { color:#edf3fb; font-size:2rem; line-height:1.05; font-weight:800; letter-spacing:-.04em; }
        .paper-subtitle { color:#8b98a9; margin-top:.45rem; font-size:.92rem; }
        .live-pill { color:#8ff0c8; background:#103d32; border:1px solid #1d735d; border-radius:999px; padding:.45rem .72rem; white-space:nowrap; font-size:.78rem; font-weight:700; }
        .live-dot { display:inline-block; width:7px; height:7px; background:#30d39a; border-radius:50%; margin-right:7px; box-shadow:0 0 12px #30d39a; }
        .section-label { color:#718094; font-size:.7rem; text-transform:uppercase; letter-spacing:.14em; font-weight:800; margin:1.3rem 0 .45rem; }
        .quote-symbol { color:#8291a4; font-size:.75rem; padding:.4rem .55rem; border:1px solid #273342; border-radius:7px; background:#0f161e; display:inline-block; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _expiry_choices(chain: pd.DataFrame) -> list[dict]:
    """Normalize FYERS expiryData into sorted UI choices."""
    choices = []
    for item in (chain.attrs.get("expiry_data", []) if isinstance(chain, pd.DataFrame) else []):
        if not isinstance(item, dict):
            continue
        raw_date = item.get("date") or item.get("expiry_date") or item.get("expiry")
        request_value = item.get("expiry") or item.get("timestamp") or item.get("date") or ""
        parsed = None
        try:
            if isinstance(raw_date, (int, float)) or str(raw_date).isdigit():
                number = float(raw_date)
                if number > 1_000_000_000:
                    parsed = pd.Timestamp(number, unit="s", tz="Asia/Kolkata").date()
            if parsed is None:
                parsed = pd.to_datetime(raw_date, errors="coerce").date()
        except Exception:
            parsed = None
        label = parsed.strftime("%d %b %Y") if parsed else str(raw_date or request_value)
        if label and label not in {choice["label"] for choice in choices}:
            choices.append({"label": label, "timestamp": str(request_value), "sort": parsed or datetime.max.date()})
    choices.sort(key=lambda choice: choice["sort"])
    return choices


def _slot_number(name: str) -> int:
    try:
        return max(1, int(str(name).rsplit("-", 1)[-1]))
    except (TypeError, ValueError):
        return 1


def _sync_expiry_slots(store: PaperTradingStore, chain_loader, client) -> None:
    """Keep Slot 1..4 aligned with the next four live expiries per index."""
    if chain_loader is None:
        return
    current = store.portfolios()
    for instrument in ("NIFTY", "BANKNIFTY", "SENSEX"):
        try:
            probe = chain_loader(client, INDEX_CONFIG[instrument]["spot"], 25, "")
        except Exception:
            continue
        choices = _expiry_choices(probe)
        if not choices:
            continue
        rows = current[current["instrument"] == instrument]
        for row in rows.itertuples():
            slot = _slot_number(row.name)
            choice = choices[min(slot - 1, len(choices) - 1)]
            if (row.expiry or "") != choice["label"]:
                store.update_portfolio(row.id, expiry=choice["label"])


def render_paper_trading(client, quote_loader, chain_loader=None) -> None:
    _inject_theme()
    st.markdown(
        """
        <div class="paper-hero">
          <div><div class="paper-kicker">Option Terminal / Simulation Desk</div>
          <div class="paper-title">Paper Trading Console</div>
          <div class="paper-subtitle">12 isolated portfolios · live FYERS market data · simulated execution only</div></div>
          <div class="live-pill"><span class="live-dot"></span>LIVE DATA</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    store = PaperTradingStore()
    _sync_expiry_slots(store, chain_loader, client)
    portfolios, portfolio_id = _portfolio_selector(store)
    portfolio = store.portfolio(portfolio_id)

    instrument = portfolio["instrument"]
    config = INDEX_CONFIG[instrument]
    try:
        chain_probe = chain_loader(client, config["spot"], 25, "") if chain_loader else OptionChain(client).fetch(config["spot"], strikecount=25)
    except Exception as exc:
        st.error(f"Unable to load live {instrument} option chain: {exc}")
        chain_probe = pd.DataFrame()

    expiry_choices = _expiry_choices(chain_probe)
    if not expiry_choices:
        fallback = sorted(chain_probe["expiry"].dropna().astype(str).unique().tolist()) if not chain_probe.empty and "expiry" in chain_probe else ["Current"]
        expiry_choices = [{"label": label, "timestamp": "", "sort": datetime.max.date()} for label in fallback]
    expiry_labels = [choice["label"] for choice in expiry_choices]
    default_expiry = portfolio["expiry"] if portfolio["expiry"] in expiry_labels else expiry_labels[min(_slot_number(portfolio["name"]) - 1, len(expiry_labels) - 1)]
    selected_expiry = st.selectbox("Assigned expiry · slot-linked", expiry_labels, index=expiry_labels.index(default_expiry), key=f"ticket_expiry:{portfolio_id}")
    selected_expiry_data = next(choice for choice in expiry_choices if choice["label"] == selected_expiry)
    try:
        chain = chain_loader(client, config["spot"], 25, selected_expiry_data["timestamp"]) if chain_loader and selected_expiry_data["timestamp"] else chain_probe
    except Exception as exc:
        st.error(f"Unable to load {selected_expiry} option chain: {exc}")
        chain = pd.DataFrame()

    # Resolve the current symbol universe before processing pending orders.
    position_symbols = _quote_symbols(store, portfolio_id)
    chain_symbols = chain["symbol"].dropna().tolist() if not chain.empty and "symbol" in chain else []
    live_quotes = quote_loader(client, sorted(set(position_symbols + chain_symbols))) if (position_symbols or chain_symbols) else {}
    filled = store.process_pending(live_quotes)
    if filled:
        st.toast(f"Filled {filled} pending paper order(s)")
    store.snapshot(portfolio_id, live_quotes)
    stats = store.stats(portfolio_id, live_quotes)

    st.markdown('<div class="section-label">Portfolio snapshot</div>', unsafe_allow_html=True)
    metric_cols = st.columns(6, gap="small")
    metric_cols[0].metric("Equity", _money(stats["equity"]))
    metric_cols[1].metric("Cash", _money(stats["cash"]))
    metric_cols[2].metric("Unrealized P&L", _money(stats["unrealized_pnl"]))
    metric_cols[3].metric("Available Margin", _money(stats["available_margin"]))
    metric_cols[4].metric("Open Positions", len(stats["positions"]))
    metric_cols[5].metric("Pending Orders", int((store.orders(portfolio_id)["status"] == "PENDING").sum()))

    with st.expander("Portfolio controls · risk limits · expiry assignment", expanded=False):
        setting_cols = st.columns(4)
        setting_cols[0].text_input("Assigned expiry · automatic", value=portfolio["expiry"] or selected_expiry, disabled=True, key=f"expiry:{portfolio_id}")
        capital = setting_cols[1].number_input("Starting capital", min_value=1000.0, value=float(portfolio["initial_capital"]), step=10000.0, key=f"capital:{portfolio_id}")
        max_loss = setting_cols[2].number_input("Max daily loss", min_value=0.0, value=float(portfolio["max_daily_loss"]), step=1000.0, key=f"loss:{portfolio_id}")
        max_order = setting_cols[3].number_input("Max order value", min_value=1000.0, value=float(portfolio["max_order_value"]), step=10000.0, key=f"order_limit:{portfolio_id}")
        if st.button("Save portfolio settings", key=f"save_settings:{portfolio_id}"):
            store.update_portfolio(portfolio_id, initial_capital=capital, max_daily_loss=max_loss, max_order_value=max_order)
            st.success("Portfolio settings saved")

    st.markdown(f'<div class="section-label">Execution ticket · {instrument}</div>', unsafe_allow_html=True)
    if chain.empty:
        st.warning("No option contracts are available from FYERS at the moment.")
        chain_view = pd.DataFrame()
    else:
        chain_view = chain.copy()
        chain_view["expiry"] = selected_expiry

    if chain_view.empty:
        return

    chain_view["contract"] = chain_view.apply(
        lambda row: f"{row['strike']:g} {row['type']} · {row['symbol']}", axis=1
    )
    contract_options = chain_view["contract"].tolist()
    selected_contract = st.selectbox("Contract", contract_options, key=f"ticket_contract:{portfolio_id}")
    contract = chain_view[chain_view["contract"] == selected_contract].iloc[0]
    symbol = contract["symbol"]
    quote = live_quotes.get(symbol) or quote_loader(client, [symbol]).get(symbol, {})
    ltp = float(quote.get("ltp") or contract.get("ltp") or 0)
    chain_ltp = float(contract.get("ltp") or 0)
    qcols = st.columns(5, gap="small")
    qcols[0].metric("LTP", _money(ltp))
    qcols[1].metric("Bid", _money(quote.get("bid")))
    qcols[2].metric("Ask", _money(quote.get("ask")))
    qcols[3].metric("OI", f"{float(contract.get('oi', 0) or 0):,.0f}")
    qcols[4].metric("IV", f"{float(contract.get('iv', 0) or 0):,.2f}")
    st.markdown(f'<div class="quote-symbol">{symbol} · live quote refreshed separately from chain snapshot</div>', unsafe_allow_html=True)
    if chain_ltp and ltp and abs(chain_ltp - ltp) > 0.01:
        st.warning(f"FYERS chain snapshot differs from the live quote by {_money(ltp - chain_ltp)} ({((ltp - chain_ltp) / chain_ltp) * 100:+.2f}%). The live quote is used for the cross-check.")

    with st.form(f"order_form:{portfolio_id}", clear_on_submit=False):
        order_cols = st.columns(7)
        side = order_cols[0].selectbox("Side", ["BUY", "SELL"], key=f"side:{portfolio_id}")
        order_type = order_cols[1].selectbox("Order type", ["MARKET", "LIMIT", "SL", "SL-M"], key=f"type:{portfolio_id}")
        quantity = order_cols[2].number_input("Quantity", min_value=1, value=1, step=1, key=f"qty:{portfolio_id}")
        product = order_cols[3].selectbox("Product", ["MIS", "NRML"], key=f"product:{portfolio_id}")
        price_source = order_cols[4].selectbox("Paper fill price", ["Manual paper price", "Live market bid/ask"], key=f"price_source:{portfolio_id}")
        price = order_cols[5].number_input("Manual price / trigger", min_value=0.0, value=float(ltp), step=0.05, format="%.2f", key=f"price:{portfolio_id}")
        tag = order_cols[6].text_input("Trade tag", value="manual", key=f"tag:{portfolio_id}")
        submitted = st.form_submit_button("Place paper order", type="primary")
    tolerance = st.number_input("Manual-price warning threshold (%)", min_value=0.1, max_value=100.0, value=5.0, step=0.5, key=f"price_tolerance:{portfolio_id}")
    manual_difference = ((price - ltp) / ltp) * 100 if price_source == "Manual paper price" and ltp else 0.0
    if price_source == "Manual paper price":
        st.info(f"Manual paper price: {_money(price)} · Live LTP: {_money(ltp)} · Difference: {manual_difference:+.2f}%")
    confirm_difference = st.checkbox("Confirm manual price if it differs beyond the warning threshold", key=f"confirm_price:{portfolio_id}")
    if submitted:
        try:
            if price_source == "Manual paper price" and abs(manual_difference) > tolerance and not confirm_difference:
                raise ValueError("Manual price differs materially from the live quote. Confirm the cross-check before placing the paper order.")
            result = store.submit_order(
                portfolio_id,
                {
                    "instrument": instrument,
                    "expiry": str(contract.get("expiry", "")),
                    "symbol": symbol,
                    "option_type": contract["type"],
                    "strike": float(contract["strike"]),
                    "side": side,
                    "quantity": int(quantity),
                    "order_type": order_type,
                    "limit_price": float(price) if order_type == "LIMIT" else None,
                    "stop_price": float(price) if order_type in {"SL", "SL-M"} else None,
                    "execution_price": float(price) if price_source == "Manual paper price" and order_type == "MARKET" else None,
                    "product": product,
                    "tag": tag,
                    "reason": f"price_source={price_source};live_ltp={ltp:.2f};manual_price={price:.2f}",
                },
                quote,
            )
            st.success(f"{result['status']}: {side} {quantity} {symbol}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.markdown('<div class="section-label">Portfolio activity</div>', unsafe_allow_html=True)
    tabs = st.tabs(["Positions", "Orders", "All-portfolios overview", "Reports"])
    with tabs[0]:
        positions = store.positions(portfolio_id)
        if positions.empty:
            st.info("No open positions in this portfolio.")
        else:
            display = positions.copy()
            display["LTP"] = display["symbol"].map(lambda item: (live_quotes.get(item) or {}).get("ltp"))
            display["Unrealized P&L"] = (display["quantity"] * (display["LTP"] - display["average_price"])).round(2)
            display = display.rename(
                columns={
                    "symbol": "Contract",
                    "expiry": "Expiry",
                    "option_type": "Type",
                    "strike": "Strike",
                    "quantity": "Qty",
                    "average_price": "Avg Price",
                    "realized_pnl": "Realized P&L",
                }
            )
            display = display[["Contract", "Expiry", "Type", "Strike", "Qty", "Avg Price", "LTP", "Unrealized P&L", "Realized P&L"]]
            st.dataframe(display, use_container_width=True, hide_index=True)
    with tabs[1]:
        orders = store.orders(portfolio_id)
        if not orders.empty:
            pending = orders[orders["status"].isin(["PENDING", "PARTIAL"])]
            if not pending.empty:
                cancel_id = st.selectbox("Pending order to cancel", pending["id"].tolist(), key=f"cancel:{portfolio_id}")
                if st.button("Cancel selected order", key=f"cancel_button:{portfolio_id}"):
                    store.cancel_order(cancel_id)
                    st.rerun()
            order_display = orders.drop(columns=["portfolio_id", "id"], errors="ignore").rename(
                columns={"created_at": "Created", "symbol": "Contract", "side": "Side", "quantity": "Qty", "filled_quantity": "Filled", "order_type": "Type", "average_fill": "Avg Fill", "status": "Status", "tag": "Tag"}
            )
            keep = [column for column in ["Created", "Contract", "Side", "Qty", "Filled", "Type", "Avg Fill", "Status", "Tag"] if column in order_display]
            st.dataframe(order_display[keep], use_container_width=True, hide_index=True)
        else:
            st.info("No orders yet.")
    with tabs[2]:
        overview = []
        for row in portfolios.itertuples():
            row_quotes = quote_loader(client, [item["symbol"] for item in store.stats(row.id).get("positions", [])]) if False else live_quotes
            row_stats = store.stats(row.id, row_quotes)
            overview.append({"Portfolio": row.name, "Instrument": row.instrument, "Expiry": row.expiry or "Unassigned", "Equity": row_stats["equity"], "Cash": row_stats["cash"], "Unrealized P&L": row_stats["unrealized_pnl"], "Open positions": len(row_stats["positions"])})
        overview_frame = pd.DataFrame(overview).rename(columns={"Portfolio": "Portfolio", "Instrument": "Index", "Expiry": "Assigned Expiry", "Unrealized P&L": "Unrealized P&L", "Open positions": "Open Positions"})
        st.dataframe(overview_frame, use_container_width=True, hide_index=True)
    with tabs[3]:
        st.caption("Exports include separate sheets for portfolios, orders, fills, and positions.")
        export_cols = st.columns(2)
        csv_data = store.export(portfolio_id, "csv")
        export_cols[0].download_button("Download portfolio CSV", csv_data, file_name=f"{portfolio['name']}_paper_trades.csv", mime="text/csv")
        try:
            xlsx_data = store.export(portfolio_id, "xlsx")
            export_cols[1].download_button("Download portfolio Excel", xlsx_data, file_name=f"{portfolio['name']}_paper_trades.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as exc:
            export_cols[1].warning(f"Excel export unavailable: {exc}")
        st.download_button("Download all 12 portfolios CSV", store.export(None, "csv"), file_name="all_paper_trades.csv", mime="text/csv")
        with st.expander("Reset this paper portfolio", expanded=False):
            st.warning("This removes its paper orders, fills, positions, and snapshots. It does not affect FYERS.")
            confirm = st.checkbox("I understand this cannot be undone", key=f"reset_confirm:{portfolio_id}")
            if st.button("Reset selected portfolio", disabled=not confirm, key=f"reset:{portfolio_id}"):
                store.reset_portfolio(portfolio_id)
                st.success("Paper portfolio reset")
                st.rerun()
