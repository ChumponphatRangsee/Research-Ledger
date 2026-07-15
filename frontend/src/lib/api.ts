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

export async function fetchInbox(status = "pending_review"): Promise<InboxItem[]> {
  const res = await fetch(`${API_URL}/api/analysis/inbox?status=${status}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch inbox");
  const data = await res.json();
  return data.items;
}

export async function approveInboxItem(id: string, userId: string) {
  const res = await fetch(`${API_URL}/api/analysis/inbox/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!res.ok) throw new Error("Failed to approve");
  return res.json();
}

export async function discardInboxItem(id: string, userId: string) {
  const res = await fetch(`${API_URL}/api/analysis/inbox/${id}/discard`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!res.ok) throw new Error("Failed to discard");
  return res.json();
}
