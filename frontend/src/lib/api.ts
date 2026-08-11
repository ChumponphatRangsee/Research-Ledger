"use client";

import { createClient } from "@/lib/supabase/client";

export type InboxItem = {
  id: string;
  status: string;
  pipeline_stage: string;
  quantitative_score: number | null;
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

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

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

async function parseResponse<T>(res: Response, fallbackMessage: string): Promise<T> {
  if (!res.ok) {
    let message = fallbackMessage;
    try {
      const data = await res.json();
      message = data.detail ?? fallbackMessage;
    } catch {
      // Non-JSON error responses still carry a useful status code.
    }
    throw new ApiError(message, res.status);
  }
  return res.json();
}

export async function fetchInbox(status = "pending_review"): Promise<InboxItem[]> {
  const res = await fetch(`${API_URL}/api/analysis/inbox?status=${status}`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  const data = await parseResponse<{ items: InboxItem[] }>(res, "Failed to fetch inbox");
  return data.items;
}

export async function approveInboxItem(id: string) {
  const res = await fetch(`${API_URL}/api/analysis/inbox/${id}/approve`, {
    method: "POST",
    headers: await authHeaders(),
  });
  return parseResponse(res, "Failed to approve");
}

export async function discardInboxItem(id: string) {
  const res = await fetch(`${API_URL}/api/analysis/inbox/${id}/discard`, {
    method: "POST",
    headers: await authHeaders(),
  });
  return parseResponse(res, "Failed to discard");
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
  const data = await parseResponse<{ holdings: PortfolioHolding[] }>(res, "Failed to fetch portfolio");
  return data.holdings;
}

export async function createPaperHoldingFromInbox(
  id: string,
  body: { shares: number; cost_basis?: number | null; notes?: string | null }
) {
  const res = await fetch(`${API_URL}/api/portfolio/execute/${id}`, {
    method: "POST",
    headers: await authHeaders(true),
    body: JSON.stringify(body),
  });
  return parseResponse(res, "Failed to create paper holding");
}

export type LedgerPosition = {
  investment_account_id: string;
  investment_account_name: string | null;
  asset_id: string;
  asset_symbol: string | null;
  asset_type: string | null;
  asset_currency: string | null;
  quantity: string;
  cost_basis_thb: string;
  weighted_average_cost_thb: string | null;
  realized_pnl_thb: string;
  income_thb: string;
  fees_thb: string;
  cash_flow_thb: string;
  market_value_thb: string | null;
  unrealized_pnl_thb: string | null;
  allocation_pct: string | null;
};

export type LedgerSummary = {
  total_cost_basis_thb: string;
  total_realized_pnl_thb: string;
  total_income_thb: string;
  total_market_value_thb: string | null;
  positions: LedgerPosition[];
};

export async function fetchLedgerSummary(): Promise<LedgerSummary> {
  const res = await fetch(`${API_URL}/api/portfolio/ledger/summary`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  return parseResponse<LedgerSummary>(res, "Failed to fetch ledger summary");
}

export type TransactionDraftStatus = "pending" | "confirmed" | "all";

export type TransactionDraft = {
  id: string;
  user_id: string;
  investment_account_id: string;
  asset_id: string;
  import_batch_id: string | null;
  reversal_of_transaction_id: string | null;
  transaction_type: string;
  transaction_at: string;
  quantity: string | number | null;
  unit_price: string | number | null;
  gross_amount: string | number | null;
  fee_amount: string | number | null;
  fee_unit: string | null;
  currency: string;
  fx_rate_to_thb: string | number | null;
  source_type: string;
  source_identifier: string | null;
  source_row_number: number | null;
  source_fingerprint: string | null;
  raw_source_data: Record<string, unknown>;
  source_metadata: Record<string, unknown>;
  notes: string | null;
  created_at: string;
  updated_at: string;
  status: "pending" | "confirmed";
  confirmed_transaction_id: string | null;
  investment_accounts: {
    name: string | null;
    account_type: string | null;
  } | null;
  assets: {
    symbol: string | null;
    name: string | null;
    asset_type: string | null;
    currency: string | null;
  } | null;
};

export async function fetchTransactionDrafts(
  status: TransactionDraftStatus = "pending",
  importBatchId?: string | null
): Promise<TransactionDraft[]> {
  const params = new URLSearchParams({ status });
  if (importBatchId) params.set("import_batch_id", importBatchId);
  const res = await fetch(`${API_URL}/api/portfolio/transaction-drafts?${params}`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  const data = await parseResponse<{ drafts: TransactionDraft[] }>(
    res,
    "Failed to fetch transaction drafts"
  );
  return data.drafts;
}

export async function confirmTransactionDraft(id: string) {
  const res = await fetch(`${API_URL}/api/portfolio/transaction-drafts/${id}/confirm`, {
    method: "POST",
    headers: await authHeaders(),
  });
  return parseResponse<{ status: string; transaction: Record<string, unknown> }>(
    res,
    "Failed to confirm transaction draft"
  );
}

export async function runScreener() {
  const res = await fetch(`${API_URL}/api/screener/run`, {
    method: "POST",
    headers: await authHeaders(),
  });
  return parseResponse<{ task_id: string; status: string }>(res, "Failed to run screener");
}

export async function runSectorScreener(topNCandidates = 20) {
  const res = await fetch(`${API_URL}/api/screener/run`, {
    method: "POST",
    headers: await authHeaders(true),
    body: JSON.stringify({ top_n_candidates: topNCandidates }),
  });
  return parseResponse<{ task_id: string; status: string }>(res, "Failed to run screener");
}

export async function triggerPipeline(body: { ticker_symbol: string; screening_run_id?: string | null }) {
  const res = await fetch(`${API_URL}/api/screener/pipeline`, {
    method: "POST",
    headers: await authHeaders(true),
    body: JSON.stringify(body),
  });
  return parseResponse(res, "Failed to trigger pipeline");
}

export type ScreeningRun = {
  id: string;
  status: "running" | "completed" | "failed";
  criteria: {
    top_n_candidates?: number;
    min_score?: number;
    min_confidence?: number;
    min_market_cap?: number;
    strategy_version?: number;
  };
  requested_count: number;
  processed_count: number;
  failed_count: number;
  passed_count: number;
  selected_count: number;
  triggered_count: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
};

export type ScreeningResult = {
  id: string;
  business_model: string;
  passed: boolean;
  total_score: number | null;
  confidence_score: number;
  quality_score: number | null;
  growth_score: number | null;
  financial_strength_score: number | null;
  valuation_score: number | null;
  sector_specific_score: number | null;
  metrics: Record<string, unknown>;
  score_breakdown: Record<string, unknown>;
  strengths: string[];
  warnings: string[];
  failure_reasons: string[];
  tickers: {
    symbol: string;
    name: string | null;
    sector: string | null;
    industry: string | null;
  } | null;
};

export async function fetchLatestScreeningRun(): Promise<ScreeningRun | null> {
  const res = await fetch(`${API_URL}/api/screener/runs/latest`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  if (res.status === 404) return null;
  return parseResponse<ScreeningRun>(res, "Failed to fetch screening run");
}

export async function fetchScreeningResults(runId: string): Promise<ScreeningResult[]> {
  const res = await fetch(
    `${API_URL}/api/screener/runs/${runId}/results?limit=500&sort=total_score_desc`,
    { headers: await authHeaders(), cache: "no-store" }
  );
  const data = await parseResponse<{ items: ScreeningResult[] }>(
    res,
    "Failed to fetch screening results"
  );
  return data.items;
}
