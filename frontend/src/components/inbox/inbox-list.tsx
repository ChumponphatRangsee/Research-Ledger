"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BriefcaseBusiness,
  Check,
  ChevronDown,
  Inbox,
  Loader2,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ApiError,
  approveInboxItem,
  createPaperHoldingFromInbox,
  discardInboxItem,
  fetchInbox,
  fetchPortfolio,
  type InboxItem,
} from "@/lib/api";

type InboxTab = "pending" | "approved" | "executed" | "rejected";

const tabs: Array<{ id: InboxTab; label: string }> = [
  { id: "pending", label: "Pending" },
  { id: "approved", label: "Approved" },
  { id: "executed", label: "Executed" },
  { id: "rejected", label: "Rejected" },
];

function apiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return "Please sign in again to continue.";
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

function recommendationBadgeClass(rec: string | null) {
  const normalized = rec?.toUpperCase();
  if (normalized === "BUY") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400";
  }
  if (normalized === "HOLD") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400";
  }
  if (normalized === "SELL" || normalized === "PASS") {
    return "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-400";
  }
  return "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-400";
}

function formatMoney(value: number | null) {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function displayLabel(value: string | null | undefined) {
  if (!value) return "—";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function InboxList() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [executedIds, setExecutedIds] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<InboxTab>("pending");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [shares, setShares] = useState("");
  const [costBasis, setCostBasis] = useState("");
  const [notes, setNotes] = useState("");

  const load = useCallback(async () => {
    try {
      setError(null);
      const [pending, approved, rejected, holdings] = await Promise.all([
        fetchInbox("pending_review"),
        fetchInbox("approved"),
        fetchInbox("discarded"),
        fetchPortfolio(),
      ]);
      const nextExecutedIds = new Set(
        holdings
          .map((holding) => holding.approved_from_inbox_id)
          .filter((id): id is string => Boolean(id))
      );
      const allItems = [...pending, ...approved, ...rejected].sort(
        (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)
      );
      setItems(allItems);
      setExecutedIds(nextExecutedIds);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not load inbox. Is the backend running?"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const counts = useMemo(
    () => ({
      pending: items.filter((item) => item.status === "pending_review").length,
      approved: items.filter(
        (item) => item.status === "approved" && !executedIds.has(item.id)
      ).length,
      executed: items.filter(
        (item) => item.status === "approved" && executedIds.has(item.id)
      ).length,
      rejected: items.filter((item) => item.status === "discarded").length,
    }),
    [executedIds, items]
  );

  const visibleItems = useMemo(() => {
    if (activeTab === "pending") {
      return items.filter((item) => item.status === "pending_review");
    }
    if (activeTab === "approved") {
      return items.filter(
        (item) => item.status === "approved" && !executedIds.has(item.id)
      );
    }
    if (activeTab === "executed") {
      return items.filter(
        (item) => item.status === "approved" && executedIds.has(item.id)
      );
    }
    return items.filter((item) => item.status === "discarded");
  }, [activeTab, executedIds, items]);

  const selectedItem = useMemo(
    () =>
      visibleItems.find((item) => item.id === selectedId) ??
      visibleItems[0] ??
      null,
    [selectedId, visibleItems]
  );

  useEffect(() => {
    setSelectedId((current) =>
      current && visibleItems.some((item) => item.id === current)
        ? current
        : visibleItems[0]?.id ?? null
    );
  }, [visibleItems]);

  useEffect(() => {
    setShares("");
    setCostBasis("");
    setNotes("");
  }, [selectedItem?.id]);

  const handleApprove = async (id: string) => {
    setActionId(id);
    try {
      setError(null);
      setNotice(null);
      await approveInboxItem(id);
      setItems((previous) =>
        previous.map((item) => (item.id === id ? { ...item, status: "approved" } : item))
      );
      setNotice("Analysis approved. Enter paper-position details to continue.");
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to approve item."));
    } finally {
      setActionId(null);
    }
  };

  const handleDiscard = async (id: string) => {
    setActionId(id);
    try {
      setError(null);
      setNotice(null);
      await discardInboxItem(id);
      setItems((previous) =>
        previous.map((item) => (item.id === id ? { ...item, status: "discarded" } : item))
      );
      setNotice("Analysis rejected and moved to the rejected queue.");
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to discard item."));
    } finally {
      setActionId(null);
    }
  };

  const handleCreatePaperHolding = async (id: string) => {
    const parsedShares = Number(shares);
    const parsedCostBasis = costBasis.trim() === "" ? null : Number(costBasis);

    if (!Number.isFinite(parsedShares) || parsedShares <= 0) {
      setError("Shares must be greater than zero.");
      return;
    }
    if (parsedCostBasis != null && (!Number.isFinite(parsedCostBasis) || parsedCostBasis < 0)) {
      setError("Cost basis must be zero or greater.");
      return;
    }

    setActionId(id);
    try {
      setError(null);
      setNotice(null);
      await createPaperHoldingFromInbox(id, {
        shares: parsedShares,
        cost_basis: parsedCostBasis,
        notes: notes.trim() || null,
      });
      setExecutedIds((previous) => new Set(previous).add(id));
      setNotice("Paper position created. It is now visible in your portfolio.");
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to create paper position."));
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
      <div className="space-y-4">
        <Card className="border-destructive/30">
          <CardContent className="p-6">
            <h2 className="text-lg font-semibold">Inbox action needs attention</h2>
            <p className="mt-2 text-sm text-muted-foreground">{error}</p>
            <Button className="mt-4" variant="outline" onClick={() => void load()}>
              Reload inbox
            </Button>
          </CardContent>
        </Card>
        {items.length > 0 && (
          <Button variant="ghost" onClick={() => setError(null)}>
            Return to loaded analyses
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div
        className="flex items-center gap-1 overflow-x-auto border-b"
        role="tablist"
        aria-label="Analysis status filters"
      >
        {tabs.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex h-10 shrink-0 items-center gap-2 px-3 text-sm font-medium transition-colors ${
                active
                  ? "text-foreground after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] tabular-nums ${
                  active ? "bg-primary/10 text-primary" : "bg-muted"
                }`}
              >
                {counts[tab.id]}
              </span>
            </button>
          );
        })}
      </div>

      {notice && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-800 dark:text-emerald-300">
          {notice}
        </div>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.6fr)]">
        <Card className="overflow-hidden">
          <div className="border-b px-4 py-3">
            <p className="text-sm font-semibold">Analysis queue</p>
            <p className="text-xs text-muted-foreground">
              {visibleItems.length} {visibleItems.length === 1 ? "item" : "items"} in{" "}
              {tabs.find((tab) => tab.id === activeTab)?.label.toLowerCase()}
            </p>
          </div>
          <div className="divide-y">
            {visibleItems.length === 0 && (
              <div className="flex min-h-48 flex-col items-center justify-center p-6 text-center">
                <Inbox className="h-5 w-5 text-muted-foreground" />
                <p className="mt-3 text-sm font-medium">
                  No {tabs.find((tab) => tab.id === activeTab)?.label.toLowerCase()} analyses
                </p>
                <p className="mt-1 max-w-xs text-xs leading-5 text-muted-foreground">
                  Records will appear here as they move through the human-review workflow.
                </p>
              </div>
            )}
            {visibleItems.map((item) => {
              const isSelected = selectedItem?.id === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  className={`w-full p-4 text-left transition-colors hover:bg-muted/50 ${
                    isSelected ? "bg-accent/70" : ""
                  }`}
                  aria-pressed={isSelected}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">{item.tickers?.symbol ?? "—"}</span>
                        <Badge
                          className={recommendationBadgeClass(item.recommendation)}
                          variant="outline"
                        >
                          {displayLabel(item.recommendation ?? "Watch")}
                        </Badge>
                      </div>
                      <p className="mt-1 truncate text-sm text-muted-foreground">
                        {item.tickers?.name ?? "Unknown company"}
                      </p>
                    </div>
                    <Badge variant={item.status === "approved" ? "default" : "secondary"}>
                      {executedIds.has(item.id)
                        ? "Paper holding"
                        : item.status === "approved"
                          ? "Approved"
                          : item.status === "discarded"
                            ? "Rejected"
                            : "Review"}
                    </Badge>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">
                      {item.tickers?.sector ?? "Sector unavailable"}
                    </span>
                    <span
                      className={
                        item.upside_pct == null
                          ? "text-muted-foreground"
                          : item.upside_pct >= 0
                            ? "text-emerald-700 dark:text-emerald-400"
                            : "text-rose-700 dark:text-rose-400"
                      }
                    >
                      {item.upside_pct == null
                        ? "Upside —"
                        : `${item.upside_pct >= 0 ? "Upside" : "Downside"} ${Math.abs(
                            Number(item.upside_pct)
                          ).toFixed(1)}%`}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </Card>

        {selectedItem && (
          <Card>
            <CardContent className="p-5 sm:p-6">
              <div className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-2xl font-semibold">{selectedItem.tickers?.symbol ?? "—"}</h2>
                    <Badge
                      className={recommendationBadgeClass(selectedItem.recommendation)}
                      variant="outline"
                    >
                      {displayLabel(selectedItem.recommendation ?? "Watch")}
                    </Badge>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {selectedItem.tickers?.name ?? "Unknown company"}
                    <span aria-hidden="true"> · </span>
                    {selectedItem.tickers?.sector ?? "Sector unavailable"}
                  </p>
                </div>
                <Badge variant={selectedItem.status === "approved" ? "default" : "secondary"}>
                  {executedIds.has(selectedItem.id)
                    ? "Paper holding created"
                    : selectedItem.status === "approved"
                      ? "Approved"
                      : selectedItem.status === "discarded"
                        ? "Rejected"
                        : "Pending review"}
                </Badge>
              </div>

              <dl className="grid grid-cols-2 gap-x-4 gap-y-5 border-b py-5 sm:grid-cols-3">
                {[
                  ["Current price", formatMoney(selectedItem.current_price)],
                  ["Fair value", formatMoney(selectedItem.fair_value)],
                  [
                    "Price potential",
                    selectedItem.upside_pct == null
                      ? "—"
                      : `${selectedItem.upside_pct >= 0 ? "Upside" : "Downside"} ${Math.abs(
                          Number(selectedItem.upside_pct)
                        ).toFixed(1)}%`,
                  ],
                  [
                    "Quant score",
                    selectedItem.quantitative_score == null
                      ? "—"
                      : Number(selectedItem.quantitative_score).toFixed(1),
                  ],
                  ["Pipeline", displayLabel(selectedItem.pipeline_stage)],
                  ["Created", formatDate(selectedItem.created_at)],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {label}
                    </dt>
                    <dd className="mt-1 text-sm font-semibold">{value}</dd>
                  </div>
                ))}
              </dl>

              <section className="py-5">
                <h3 className="text-sm font-semibold">Analysis summary</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {selectedItem.memo_summary || "No analysis summary is available."}
                </p>
                <details className="group mt-4 rounded-lg border bg-muted/20">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium">
                    Review full investment memo
                    <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
                  </summary>
                  <div className="border-t px-4 py-4">
                    <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-sans text-sm leading-6 text-muted-foreground">
                      {selectedItem.investment_memo || "No detailed memo is available."}
                    </pre>
                  </div>
                </details>
              </section>

              {selectedItem.status === "approved" && !executedIds.has(selectedItem.id) ? (
                <form
                  className="border-t pt-5"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleCreatePaperHolding(selectedItem.id);
                  }}
                >
                  <div>
                    <h3 className="font-semibold">Paper-position details</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      This records a paper holding; it does not place a live brokerage order.
                    </p>
                  </div>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <label className="grid gap-1.5 text-sm font-medium">
                      Shares
                      <input
                        required
                        min="0.000001"
                        step="any"
                        inputMode="decimal"
                        type="number"
                        value={shares}
                        onChange={(event) => setShares(event.target.value)}
                        className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                        placeholder="10"
                      />
                    </label>
                    <label className="grid gap-1.5 text-sm font-medium">
                      Total cost basis
                      <input
                        min="0"
                        step="any"
                        inputMode="decimal"
                        type="number"
                        value={costBasis}
                        onChange={(event) => setCostBasis(event.target.value)}
                        className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                        placeholder="Optional"
                      />
                    </label>
                  </div>
                  <label className="mt-4 grid gap-1.5 text-sm font-medium">
                    Notes
                    <textarea
                      value={notes}
                      onChange={(event) => setNotes(event.target.value)}
                      className="min-h-20 resize-y rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                      placeholder="Position rationale, risks, or review date"
                    />
                  </label>
                  <div className="mt-4 flex justify-end">
                    <Button type="submit" disabled={actionId === selectedItem.id}>
                      {actionId === selectedItem.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <BriefcaseBusiness className="h-4 w-4" />
                      )}
                      Create paper holding
                    </Button>
                  </div>
                </form>
              ) : selectedItem.status === "pending_review" ? (
                <div className="flex flex-wrap justify-end gap-2 border-t pt-5">
                  <Button
                    variant="outline"
                    disabled={actionId === selectedItem.id}
                    onClick={() => void handleDiscard(selectedItem.id)}
                  >
                    {actionId === selectedItem.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <X className="h-4 w-4" />
                    )}
                    Reject
                  </Button>
                  <Button
                    disabled={actionId === selectedItem.id}
                    onClick={() => void handleApprove(selectedItem.id)}
                  >
                    {actionId === selectedItem.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                    Approve
                  </Button>
                </div>
              ) : (
                <div className="border-t pt-5">
                  <p className="text-sm text-muted-foreground">
                    {executedIds.has(selectedItem.id)
                      ? "This approved idea has already been recorded as a paper holding."
                      : "This analysis was rejected and no portfolio action is available."}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        )}
        {!selectedItem && (
          <Card className="hidden min-h-72 items-center justify-center lg:flex">
            <div className="max-w-sm p-8 text-center">
              <p className="text-sm font-medium">No analysis selected</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                Choose an analysis from the queue to inspect its research details.
              </p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
