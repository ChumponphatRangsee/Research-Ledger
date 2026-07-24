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

function formatShortDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const formatter = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "2-digit",
  });
  return formatter.format(date);
}

function displayLabel(value: string | null | undefined) {
  if (!value) return "—";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusLabel(item: InboxItem, executedIds: Set<string>) {
  if (executedIds.has(item.id)) return "Executed";
  if (item.status === "approved") return "Approved";
  if (item.status === "discarded") return "Rejected";
  return "Pending";
}

function statusBadgeClass(item: InboxItem, executedIds: Set<string>) {
  if (executedIds.has(item.id)) {
    return "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-400";
  }
  if (item.status === "approved") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400";
  }
  if (item.status === "discarded") {
    return "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-400";
  }
  return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400";
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

  if (error && items.length === 0) {
    return (
      <Card className="border-destructive/30">
        <CardContent className="flex min-h-56 flex-col items-center justify-center p-6 text-center">
          <h2 className="text-base font-semibold">Analysis inbox unavailable</h2>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">{error}</p>
          <Button className="mt-4" variant="outline" onClick={() => void load()}>
            Reload inbox
          </Button>
        </CardContent>
      </Card>
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

      {error && (
        <div
          className="flex items-center justify-between gap-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          <span>{error}</span>
          <Button size="sm" variant="ghost" onClick={() => setError(null)}>
            Dismiss
          </Button>
        </div>
      )}

      {notice && (
        <div
          className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-800 dark:text-emerald-300"
          role="status"
        >
          {notice}
        </div>
      )}

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(360px,0.7fr)]">
        <Card className="overflow-hidden">
          <div className="border-b px-4 py-3">
            <p className="text-sm font-semibold">Analysis queue</p>
            <p className="text-xs text-muted-foreground">
              {visibleItems.length} {visibleItems.length === 1 ? "item" : "items"} in{" "}
              {tabs.find((tab) => tab.id === activeTab)?.label.toLowerCase()}
            </p>
          </div>
          <div className="overflow-x-auto">
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
            {visibleItems.length > 0 && (
              <div className="min-w-[760px]">
                <div
                  className="grid grid-cols-[minmax(150px,1.5fr)_88px_70px_64px_108px_82px_86px] gap-3 border-b bg-muted/35 px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
                  aria-hidden="true"
                >
                  <span>Company</span>
                  <span>Rating</span>
                  <span className="text-right">Upside</span>
                  <span className="text-right">Score</span>
                  <span>Pipeline</span>
                  <span>Created</span>
                  <span>Status</span>
                </div>
                <div className="divide-y">
                  {visibleItems.map((item) => {
                    const isSelected = selectedItem?.id === item.id;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => setSelectedId(item.id)}
                        className={`grid w-full grid-cols-[minmax(150px,1.5fr)_88px_70px_64px_108px_82px_86px] items-center gap-3 px-3 py-3 text-left text-xs transition-colors hover:bg-muted/50 ${
                          isSelected
                            ? "bg-accent/70 shadow-[inset_3px_0_0_0_var(--color-primary)]"
                            : ""
                        }`}
                        aria-pressed={isSelected}
                      >
                        <span className="min-w-0">
                          <span className="block text-sm font-semibold">
                            {item.tickers?.symbol ?? "—"}
                          </span>
                          <span className="block truncate text-[11px] text-muted-foreground">
                            {item.tickers?.name ?? "Unknown company"}
                          </span>
                        </span>
                        <span>
                          <Badge
                            className={`${recommendationBadgeClass(item.recommendation)} px-2 py-0 text-[10px]`}
                            variant="outline"
                          >
                            {displayLabel(item.recommendation ?? "Watch")}
                          </Badge>
                        </span>
                        <span
                          className={`text-right font-medium tabular-nums ${
                            item.upside_pct == null
                              ? "text-muted-foreground"
                              : item.upside_pct >= 0
                                ? "text-emerald-700 dark:text-emerald-400"
                                : "text-rose-700 dark:text-rose-400"
                          }`}
                        >
                          {item.upside_pct == null
                            ? "—"
                            : `${item.upside_pct >= 0 ? "+" : ""}${Number(
                                item.upside_pct
                              ).toFixed(1)}%`}
                        </span>
                        <span className="text-right font-medium tabular-nums">
                          {item.quantitative_score == null
                            ? "—"
                            : Number(item.quantitative_score).toFixed(1)}
                        </span>
                        <span className="truncate text-muted-foreground">
                          {displayLabel(item.pipeline_stage)}
                        </span>
                        <span className="tabular-nums text-muted-foreground">
                          {formatShortDate(item.created_at)}
                        </span>
                        <span>
                          <Badge
                            className={`${statusBadgeClass(item, executedIds)} px-2 py-0 text-[10px]`}
                            variant="outline"
                          >
                            {statusLabel(item, executedIds)}
                          </Badge>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
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
                <Badge
                  className={statusBadgeClass(selectedItem, executedIds)}
                  variant="outline"
                >
                  {statusLabel(selectedItem, executedIds)}
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
                  <div className="max-h-80 overflow-y-auto whitespace-pre-wrap border-t px-4 py-4 text-sm leading-6 text-muted-foreground">
                      {selectedItem.investment_memo || "No detailed memo is available."}
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
                    <h3 className="font-semibold">Add to paper portfolio</h3>
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
                      Add to paper portfolio
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
