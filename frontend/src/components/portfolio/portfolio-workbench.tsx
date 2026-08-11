"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, UserCircle2 } from "lucide-react";
import Link from "next/link";

import { PortfolioList } from "@/components/portfolio/portfolio-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  confirmTransactionDraft,
  fetchLedgerSummary,
  fetchTransactionDrafts,
  type LedgerSummary,
  type TransactionDraft,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type PortfolioTab = "ledger" | "drafts" | "transactions" | "legacy";

const tabs: Array<{ id: PortfolioTab; label: string; description: string }> = [
  {
    id: "ledger",
    label: "Ledger summary",
    description: "Positions rebuilt from immutable confirmed transactions.",
  },
  {
    id: "drafts",
    label: "Draft review",
    description: "Human confirmation queue for imported or proposed transactions.",
  },
  {
    id: "transactions",
    label: "Confirmed transactions",
    description: "Confirmed draft evidence linked to immutable ledger rows.",
  },
  {
    id: "legacy",
    label: "Legacy holdings",
    description: "Existing paper holdings from approved analyses.",
  },
];

const AUTH_REQUIRED_MESSAGE = "Please sign in to view portfolio ledger data.";

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return AUTH_REQUIRED_MESSAGE;
  }
  if (error instanceof Error && error.message === "Not authenticated") {
    return AUTH_REQUIRED_MESSAGE;
  }
  if (error instanceof Error) return error.message;
  return "Could not load portfolio ledger data.";
}

function numericValue(value: string | number | null | undefined) {
  if (value == null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatDecimal(
  value: string | number | null | undefined,
  maximumFractionDigits = 6
) {
  const parsed = numericValue(value);
  if (parsed == null) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits,
  }).format(parsed);
}

function formatThb(value: string | number | null | undefined) {
  const parsed = numericValue(value);
  if (parsed == null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "THB",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeZone: "Asia/Bangkok",
  }).format(new Date(value));
}

function statusBadge(status: TransactionDraft["status"]) {
  return status === "confirmed" ? (
    <Badge className="gap-1 bg-emerald-600 text-white">
      <CheckCircle2 className="h-3 w-3" />
      Confirmed
    </Badge>
  ) : (
    <Badge variant="outline" className="gap-1 border-amber-300 bg-amber-50 text-amber-700">
      <AlertTriangle className="h-3 w-3" />
      Pending review
    </Badge>
  );
}

export function PortfolioWorkbench() {
  const [activeTab, setActiveTab] = useState<PortfolioTab>("ledger");
  const [summary, setSummary] = useState<LedgerSummary | null>(null);
  const [pendingDrafts, setPendingDrafts] = useState<TransactionDraft[]>([]);
  const [confirmedDrafts, setConfirmedDrafts] = useState<TransactionDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmingDraftId, setConfirmingDraftId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setNotice(null);
      const [ledger, pending, confirmed] = await Promise.all([
        fetchLedgerSummary(),
        fetchTransactionDrafts("pending"),
        fetchTransactionDrafts("confirmed"),
      ]);
      setSummary(ledger);
      setPendingDrafts(pending);
      setConfirmedDrafts(confirmed);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const totals = useMemo(
    () => [
      ["Cost basis", formatThb(summary?.total_cost_basis_thb)],
      ["Realized P&L", formatThb(summary?.total_realized_pnl_thb)],
      ["Income", formatThb(summary?.total_income_thb)],
      ["Marked value", formatThb(summary?.total_market_value_thb)],
    ],
    [summary]
  );

  async function handleRefresh() {
    setRefreshing(true);
    await load();
  }

  async function handleConfirm(draft: TransactionDraft) {
    try {
      setConfirmingDraftId(draft.id);
      setError(null);
      await confirmTransactionDraft(draft.id);
      setNotice(`Confirmed ${draft.source_identifier ?? draft.id}.`);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setConfirmingDraftId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading portfolio ledger...
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-4">
        {totals.map(([label, value]) => (
          <Card key={label}>
            <CardHeader className="p-4 pb-2">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {label}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <p className="text-xl font-semibold tabular-nums">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 md:flex-row md:items-center md:justify-between">
        <div className="grid gap-2 md:grid-cols-4">
          {tabs.map((tab) => {
            const active = tab.id === activeTab;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "rounded-lg border px-3 py-2 text-left transition-colors",
                  active
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-transparent text-muted-foreground hover:bg-muted"
                )}
              >
                <span className="block text-sm font-medium">{tab.label}</span>
                <span className="mt-0.5 hidden text-xs leading-4 md:block">
                  {tab.description}
                </span>
              </button>
            );
          })}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void handleRefresh()}
          disabled={refreshing}
        >
          {refreshing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Refresh
        </Button>
      </div>

      {notice && (
        <Card className="border-emerald-200 bg-emerald-50 text-emerald-900">
          <CardContent className="p-4 text-sm">{notice}</CardContent>
        </Card>
      )}

      {error && (
        <Card className="border-destructive/30">
          <CardContent className="flex flex-col gap-3 p-4 text-sm text-destructive sm:flex-row sm:items-center sm:justify-between">
            <span>{error}</span>
            {error === AUTH_REQUIRED_MESSAGE && (
              <Button variant="outline" size="sm" asChild>
                <Link href="/login?redirectTo=%2Fportfolio">
                  <UserCircle2 className="h-4 w-4" />
                  Sign in
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === "ledger" && <LedgerSummaryPanel summary={summary} />}
      {activeTab === "drafts" && (
        <DraftReviewPanel
          drafts={pendingDrafts}
          confirmingDraftId={confirmingDraftId}
          onConfirm={(draft) => void handleConfirm(draft)}
        />
      )}
      {activeTab === "transactions" && (
        <ConfirmedTransactionsPanel drafts={confirmedDrafts} />
      )}
      {activeTab === "legacy" && <PortfolioList />}
    </div>
  );
}

function LedgerSummaryPanel({ summary }: { summary: LedgerSummary | null }) {
  const positions = summary?.positions ?? [];
  return (
    <Card className="overflow-hidden">
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">Ledger-derived positions</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Rebuilt from confirmed transactions only. Market value remains empty until
          price snapshots are implemented.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-left text-sm">
          <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              {[
                "Account",
                "Asset",
                "Quantity",
                "Cost basis",
                "Average cost",
                "Realized P&L",
                "Fees",
                "Cash flow",
              ].map((heading) => (
                <th key={heading} className="px-4 py-3 font-medium">
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {positions.length === 0 && (
              <tr>
                <td colSpan={8} className="h-40 px-6 text-center text-muted-foreground">
                  No confirmed ledger positions yet.
                </td>
              </tr>
            )}
            {positions.map((position) => (
              <tr
                key={`${position.investment_account_id}-${position.asset_id}`}
                className="hover:bg-muted/30"
              >
                <td className="px-4 py-4 font-medium">
                  {position.investment_account_name ?? "Unknown account"}
                </td>
                <td className="px-4 py-4">
                  <p className="font-semibold">{position.asset_symbol ?? "—"}</p>
                  <p className="text-xs text-muted-foreground">
                    {position.asset_type ?? "Asset"} · {position.asset_currency ?? "—"}
                  </p>
                </td>
                <td className="px-4 py-4 tabular-nums">
                  {formatDecimal(position.quantity, 8)}
                </td>
                <td className="px-4 py-4 tabular-nums">
                  {formatThb(position.cost_basis_thb)}
                </td>
                <td className="px-4 py-4 tabular-nums">
                  {formatThb(position.weighted_average_cost_thb)}
                </td>
                <td className="px-4 py-4 tabular-nums">
                  {formatThb(position.realized_pnl_thb)}
                </td>
                <td className="px-4 py-4 tabular-nums">{formatThb(position.fees_thb)}</td>
                <td className="px-4 py-4 tabular-nums">
                  {formatThb(position.cash_flow_thb)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function DraftReviewPanel({
  drafts,
  confirmingDraftId,
  onConfirm,
}: {
  drafts: TransactionDraft[];
  confirmingDraftId: string | null;
  onConfirm: (draft: TransactionDraft) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">Pending transaction drafts</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Confirming creates immutable ledger transactions. Corrections require linked
          reversals.
        </p>
      </div>
      <DraftTable
        drafts={drafts}
        emptyMessage="No pending drafts. Imported rows have already been confirmed."
        action={(draft) => (
          <Button
            size="sm"
            onClick={() => onConfirm(draft)}
            disabled={confirmingDraftId === draft.id}
          >
            {confirmingDraftId === draft.id && (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
            Confirm
          </Button>
        )}
      />
    </Card>
  );
}

function ConfirmedTransactionsPanel({ drafts }: { drafts: TransactionDraft[] }) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">Confirmed imported transactions</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          This view shows confirmed draft evidence linked to ledger transaction IDs.
        </p>
      </div>
      <DraftTable
        drafts={drafts}
        emptyMessage="No confirmed imported transactions yet."
        action={(draft) => statusBadge(draft.status)}
      />
    </Card>
  );
}

function DraftTable({
  drafts,
  emptyMessage,
  action,
}: {
  drafts: TransactionDraft[];
  emptyMessage: string;
  action: (draft: TransactionDraft) => ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1120px] text-left text-sm">
        <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            {[
              "Date",
              "Source",
              "Account",
              "Asset",
              "Type",
              "Quantity",
              "Price",
              "Fee",
              "FX",
              "Ledger link",
              "Action",
            ].map((heading) => (
              <th key={heading} className="px-4 py-3 font-medium">
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {drafts.length === 0 && (
            <tr>
              <td colSpan={11} className="h-40 px-6 text-center text-muted-foreground">
                {emptyMessage}
              </td>
            </tr>
          )}
          {drafts.map((draft) => (
            <tr key={draft.id} className="align-top hover:bg-muted/30">
              <td className="px-4 py-4 tabular-nums">{formatDate(draft.transaction_at)}</td>
              <td className="px-4 py-4">
                <p className="font-medium">{draft.source_identifier ?? "—"}</p>
                <p className="text-xs text-muted-foreground">
                  Row {draft.source_row_number ?? "—"} · {draft.source_type}
                </p>
              </td>
              <td className="px-4 py-4">
                {draft.investment_accounts?.name ?? "Unknown account"}
              </td>
              <td className="px-4 py-4">
                <p className="font-semibold">{draft.assets?.symbol ?? "—"}</p>
                <p className="text-xs text-muted-foreground">
                  {draft.assets?.asset_type ?? "Asset"} · {draft.assets?.currency ?? draft.currency}
                </p>
              </td>
              <td className="px-4 py-4">
                <Badge variant="secondary">{draft.transaction_type}</Badge>
              </td>
              <td className="px-4 py-4 tabular-nums">{formatDecimal(draft.quantity, 8)}</td>
              <td className="px-4 py-4 tabular-nums">
                {formatDecimal(draft.unit_price, 8)} {draft.currency}
              </td>
              <td className="px-4 py-4 tabular-nums">
                {formatDecimal(draft.fee_amount, 8)}
                <p className="text-xs text-muted-foreground">{draft.fee_unit ?? "—"}</p>
              </td>
              <td className="px-4 py-4 tabular-nums">
                {formatDecimal(draft.fx_rate_to_thb, 6)}
              </td>
              <td className="px-4 py-4">
                {draft.confirmed_transaction_id ? (
                  <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                    {draft.confirmed_transaction_id.slice(0, 8)}
                  </code>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-4 py-4">{action(draft)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
