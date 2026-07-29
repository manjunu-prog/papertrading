-- Run once in the Supabase SQL Editor.

create table if not exists public.paper_portfolios (
  id text primary key,
  name text not null unique,
  instrument text not null,
  expiry text default '',
  initial_capital double precision not null default 100000,
  cash double precision not null default 100000,
  max_daily_loss double precision not null default 5000,
  max_order_value double precision not null default 250000,
  margin_rate double precision not null default 0.20,
  active boolean not null default true,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists public.paper_orders (
  id text primary key,
  portfolio_id text not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  instrument text not null,
  expiry text default '',
  symbol text not null,
  option_type text default '',
  strike double precision,
  side text not null,
  quantity integer not null,
  filled_quantity integer not null default 0,
  order_type text not null,
  limit_price double precision,
  stop_price double precision,
  average_fill double precision,
  status text not null,
  product text not null default 'MIS',
  tag text default '',
  reason text default ''
);

create table if not exists public.paper_fills (
  id text primary key,
  order_id text not null,
  portfolio_id text not null,
  filled_at timestamptz not null,
  symbol text not null,
  side text not null,
  quantity integer not null,
  price double precision not null,
  value double precision not null
);

create table if not exists public.paper_positions (
  portfolio_id text not null,
  symbol text not null,
  instrument text not null,
  expiry text default '',
  option_type text default '',
  strike double precision,
  quantity integer not null default 0,
  average_price double precision not null default 0,
  realized_pnl double precision not null default 0,
  updated_at timestamptz not null,
  primary key (portfolio_id, symbol)
);

create table if not exists public.paper_equity_snapshots (
  id text primary key,
  portfolio_id text not null,
  captured_at timestamptz not null,
  equity double precision not null,
  cash double precision not null,
  market_value double precision not null,
  unrealized_pnl double precision not null,
  margin_used double precision not null
);

create index if not exists paper_orders_portfolio_idx on public.paper_orders(portfolio_id, created_at);
create index if not exists paper_fills_portfolio_idx on public.paper_fills(portfolio_id, filled_at);
create index if not exists paper_snapshots_portfolio_idx on public.paper_equity_snapshots(portfolio_id, captured_at);
