"use client";

import { createClient } from "@/lib/supabase/client";

export type InboxItem = {
  id: string;
  status: string;
  recommendation: string | null;
  memo_summary: string | null;
  fair_value: number | null;
  current_price: number | null;
  upside_pct: number | null;
  investment_memo: string | null;
  created_at: string;
  tickers: {
    symbol: string;
    name: string | null;
    sector: string | null;
  } | null;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function authHeaders(includeJson = false): Promise<HeadersInit> {
  const supabase = createClient();
  const { data, error } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  if (error || !token) {
    throw new Error("Not authenticated");
  }

  return {
    ...(includeJson ? { "Content-Type": "application/json" } : {}),
    Authorization: `Bearer ${token}`,
  };
}

export async function fetchInbox(status = "pending_review"): Promise<InboxItem[]> {
  const res = await fetch(`${API_URL}/api/analysis/inbox?status=${status}`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch inbox");
  const data = await res.json();
  return data.items;
}

export async function approveInboxItem(id: string) {
  const res = await fetch(`${API_URL}/api/analysis/inbox/${id}/approve`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to approve");
  return res.json();
}

export async function discardInboxItem(id: string) {
  const res = await fetch(`${API_URL}/api/analysis/inbox/${id}/discard`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to discard");
  return res.json();
}

export type PortfolioHolding = {
  id: string;
  user_id: string;
  ticker_id: string;
  approved_from_inbox_id: string | null;
  shares: number;
  cost_basis: number | null;
  avg_cost_per_share: number | null;
  status: string;
  notes: string | null;
  tickers: {
    symbol: string;
    name: string | null;
    sector: string | null;
  } | null;
};

export async function fetchPortfolio(): Promise<PortfolioHolding[]> {
  const res = await fetch(`${API_URL}/api/portfolio/`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch portfolio");
  const data = await res.json();
  return data.holdings;
}

export async function executeFromInbox(
  id: string,
  body: { shares: number; cost_basis?: number | null; notes?: string | null }
) {
  const res = await fetch(`${API_URL}/api/portfolio/execute/${id}`, {
    method: "POST",
    headers: await authHeaders(true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to execute portfolio action");
  return res.json();
}
