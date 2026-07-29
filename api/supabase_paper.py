"""Optional Supabase persistence for the paper-trading ledger."""

from __future__ import annotations

import os
from typing import Any

import requests


def _secret(key: str) -> str:
    value = os.getenv(key, "")
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(key, "")
    except Exception:
        return ""


class SupabasePaperStore:
    tables = ("paper_portfolios", "paper_orders", "paper_fills", "paper_positions", "paper_equity_snapshots")

    def __init__(self):
        raw_url = _secret("SUPABASE_URL").strip().rstrip("/")
        self.url = raw_url.split("/rest/v1", 1)[0] if "/rest/v1" in raw_url else raw_url
        self.key = _secret("SUPABASE_SERVICE_ROLE_KEY") or _secret("SUPABASE_ANON_KEY")
        self.enabled = bool(self.url.startswith(("https://", "http://")) and self.key)

    def _headers(self, merge: bool = False) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal" if merge else "return=minimal",
        }

    def _endpoint(self, table: str) -> str:
        return f"{self.url}/rest/v1/{table}"

    def fetch_state(self) -> dict[str, list[dict[str, Any]]]:
        if not self.enabled:
            return {}
        state = {}
        try:
            for table in self.tables:
                response = requests.get(self._endpoint(table), headers=self._headers(), params={"select": "*", "limit": "10000"}, timeout=12)
                if response.status_code >= 400:
                    return {}
                state[table] = response.json()
        except (requests.RequestException, ValueError):
            return {}
        return state

    def replace_state(self, state: dict[str, list[dict[str, Any]]]) -> bool:
        if not self.enabled:
            return False
        try:
            for table in self.tables:
                delete_column = "symbol" if table == "paper_positions" else "id"
                response = requests.delete(self._endpoint(table), headers=self._headers(), params={delete_column: "not.is.null"}, timeout=15)
                if response.status_code >= 400:
                    return False
                rows = state.get(table, [])
                for start in range(0, len(rows), 500):
                    if rows[start : start + 500]:
                        response = requests.post(self._endpoint(table), headers=self._headers(merge=True), json=rows[start : start + 500], timeout=20)
                        if response.status_code >= 400:
                            return False
            return True
        except requests.RequestException:
            return False
