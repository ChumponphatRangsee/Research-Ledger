"use client";

import { useEffect, useState } from "react";
import { Check, X, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError, approveInboxItem, discardInboxItem, fetchInbox, type InboxItem } from "@/lib/api";

function apiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return "Please sign in again to continue.";
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

function recommendationBadgeClass(rec: string | null) {
  if (rec === "BUY") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400";
  if (rec === "HOLD") return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400";
  return "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-400";
}

export function InboxList() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      const data = await fetchInbox();
      setItems(data);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not load inbox. Is the backend running?"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleApprove = async (id: string) => {
    setActionId(id);
    try {
      await approveInboxItem(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to approve item."));
    } finally {
      setActionId(null);
    }
  };

  const handleDiscard = async (id: string) => {
    setActionId(id);
    try {
      await discardInboxItem(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to discard item."));
    } finally {
      setActionId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading inbox...
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="p-6">
          <h2 className="text-lg font-semibold">Error</h2>
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
          <Button className="mt-4" onClick={load}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardContent className="p-6">
          <h2 className="text-lg font-semibold">Inbox empty</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            No pending analyses. Run the daily screener or trigger a pipeline manually via the API.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      {items.map((item) => (
        <Card key={item.id}>
          <CardContent className="p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h3 className="text-lg font-semibold">{item.tickers?.symbol ?? "—"}</h3>
                  <Badge className={recommendationBadgeClass(item.recommendation)} variant="outline">
                    {item.recommendation ?? "PENDING"}
                  </Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {item.tickers?.name ?? "Unknown"} · {item.tickers?.sector ?? "—"}
                </p>
                <p className="mt-2 text-sm">{item.memo_summary}</p>
              </div>
              <div className="text-left sm:text-right">
                <p className="text-xl font-semibold">${item.fair_value?.toFixed(2) ?? "—"}</p>
                <p className="text-sm text-muted-foreground">fair value</p>
                {item.upside_pct != null && (
                  <p className={item.upside_pct >= 0 ? "text-sm text-emerald-600" : "text-sm text-rose-600"}>
                    {item.upside_pct >= 0 ? "+" : ""}{item.upside_pct.toFixed(1)}% upside
                  </p>
                )}
              </div>
            </div>

            {item.investment_memo && (
              <pre className="mt-4 max-h-40 overflow-auto rounded-lg bg-muted p-4 text-xs whitespace-pre-wrap">
                {item.investment_memo}
              </pre>
            )}

            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={actionId === item.id}
                onClick={() => handleDiscard(item.id)}
              >
                {actionId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
                Discard
              </Button>
              <Button
                size="sm"
                disabled={actionId === item.id}
                onClick={() => handleApprove(item.id)}
              >
                {actionId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                Approve &amp; Execute
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
