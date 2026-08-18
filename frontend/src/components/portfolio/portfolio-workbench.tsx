"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  Check,
  Eye,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  UserCircle2,
  X,
} from "lucide-react";
import Link from "next/link";

import { PortfolioList } from "@/components/portfolio/portfolio-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  ApiNetworkError,
  confirmTransactionDraft,
  createCorrectionDraft,
  createInvestmentAccount,
  createReversalDraft,
  fetchConfirmedTransaction,
  fetchConfirmedTransactions,
  fetchLedgerSummary,
  fetchInvestmentAccounts,
  fetchTransactionImportBatches,
  fetchTransactionImportErrors,
  fetchTransactionDrafts,
  updateTransactionDraft,
  type ConfirmedTransaction,
  type InvestmentAccount,
  type InvestmentAccountType,
  type LedgerSummary,
  type TransactionImportBatch,
  type TransactionImportError,
  type TransactionDraft,
  type TransactionDraftMutation,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type PortfolioTab =
  | "overview"
  | "positions"
  | "activity"
  | "drafts"
  | "ledger";

type LedgerView = "summary" | "accounts" | "import-errors" | "legacy";

const tabs: Array<{ id: PortfolioTab; label: string; description: string }> = [
  {
    id: "overview",
    label: "Overview",
    description: "Ownership, cost basis, performance, and items needing review.",
  },
  {
    id: "positions",
    label: "Positions",
    description: "Simplified holdings rebuilt from confirmed transactions.",
  },
  {
    id: "activity",
    label: "Activity",
    description: "Confirmed transaction history with correction and reversal workflows.",
  },
  {
    id: "drafts",
    label: "Drafts",
    description: "Human confirmation queue for imported or proposed transactions.",
  },
  {
    id: "ledger",
    label: "Ledger",
    description: "Accounting detail, accounts, import diagnostics, and archived holdings.",
  },
];

const ledgerViews: Array<{ id: LedgerView; label: string }> = [
  { id: "summary", label: "Ledger detail" },
  { id: "accounts", label: "Accounts" },
  { id: "import-errors", label: "Import errors" },
  { id: "legacy", label: "Legacy holdings" },
];

type OverviewMetric = {
  label: string;
  value: string;
  description: string;
  unavailable?: boolean;
};

type AttentionItem = {
  label: string;
  value: string;
  description: string;
  tab?: PortfolioTab;
  ledgerView?: LedgerView;
  urgent?: boolean;
};

const AUTH_REQUIRED_MESSAGE = "Please sign in to view portfolio ledger data.";
const accountTypeOptions: Array<{ value: InvestmentAccountType; label: string }> = [
  { value: "BROKERAGE", label: "Brokerage" },
  { value: "CRYPTO_EXCHANGE", label: "Crypto exchange" },
  { value: "CRYPTO_WALLET", label: "Crypto wallet" },
  { value: "BANK", label: "Bank" },
  { value: "CASH", label: "Cash" },
  { value: "OTHER", label: "Other" },
];

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return AUTH_REQUIRED_MESSAGE;
  }
  if (error instanceof Error && error.message === "Not authenticated") {
    return AUTH_REQUIRED_MESSAGE;
  }
  if (error instanceof ApiNetworkError) {
    return error.message;
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
  if (parsed == null) return "-";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits,
  }).format(parsed);
}

function formatThb(value: string | number | null | undefined) {
  const parsed = numericValue(value);
  if (parsed == null) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "THB",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatPercent(value: string | number | null | undefined) {
  const parsed = numericValue(value);
  if (parsed == null) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(parsed / 100);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeZone: "Asia/Bangkok",
  }).format(new Date(value));
}

function formatDateTimeInput(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 16);
}

function inputValue(value: string | number | null | undefined) {
  return value == null ? "" : String(value);
}

function nullableString(value: string) {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export function PortfolioWorkbench() {
  const [activeTab, setActiveTab] = useState<PortfolioTab>("overview");
  const [ledgerView, setLedgerView] = useState<LedgerView>("summary");
  const [summary, setSummary] = useState<LedgerSummary | null>(null);
  const [accounts, setAccounts] = useState<InvestmentAccount[]>([]);
  const [pendingDrafts, setPendingDrafts] = useState<TransactionDraft[]>([]);
  const [confirmedTransactions, setConfirmedTransactions] = useState<
    ConfirmedTransaction[]
  >([]);
  const [selectedTransaction, setSelectedTransaction] =
    useState<ConfirmedTransaction | null>(null);
  const [importBatches, setImportBatches] = useState<TransactionImportBatch[]>([]);
  const [importErrors, setImportErrors] = useState<TransactionImportError[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmingDraftId, setConfirmingDraftId] = useState<string | null>(null);
  const [editingDraftId, setEditingDraftId] = useState<string | null>(null);
  const [updatingDraftId, setUpdatingDraftId] = useState<string | null>(null);
  const [reversingTransactionId, setReversingTransactionId] = useState<string | null>(
    null
  );
  const [correctingTransactionId, setCorrectingTransactionId] = useState<
    string | null
  >(null);
  const [loadingTransactionDetailId, setLoadingTransactionDetailId] = useState<
    string | null
  >(null);
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setNotice(null);
      const [
        ledger,
        investmentAccounts,
        pending,
        transactions,
        batches,
        importErrorRows,
      ] = await Promise.all([
        fetchLedgerSummary(),
        fetchInvestmentAccounts(),
        fetchTransactionDrafts("pending"),
        fetchConfirmedTransactions({ limit: 200 }),
        fetchTransactionImportBatches({ limit: 25 }),
        fetchTransactionImportErrors({ limit: 200 }),
      ]);
      setSummary(ledger);
      setAccounts(investmentAccounts);
      setPendingDrafts(pending);
      setConfirmedTransactions(transactions);
      setImportBatches(batches);
      setImportErrors(importErrorRows);
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

  const overviewMetrics = useMemo<OverviewMetric[]>(
    () => [
      {
        label: "Cost basis",
        value: formatThb(summary?.total_cost_basis_thb),
        description: "Confirmed weighted cost basis in THB.",
      },
      {
        label: "Realized P&L",
        value: formatThb(summary?.total_realized_pnl_thb),
        description: "Closed-transaction result from ledger projections.",
      },
      {
        label: "Income",
        value: formatThb(summary?.total_income_thb),
        description: "Ledger income from confirmed transactions.",
      },
      {
        label: "Cash flow",
        value: formatThb(summary?.total_cash_flow_thb),
        description: "Net confirmed cash flow in portfolio base currency.",
      },
      {
        label: "Fees",
        value: formatThb(summary?.total_fees_thb),
        description: "Confirmed transaction fees in THB.",
      },
    ],
    [summary]
  );

  const marketValueMetric = useMemo<OverviewMetric>(
    () => ({
      label: "Market value",
      value:
        summary?.total_market_value_thb == null
          ? "Unavailable"
          : formatThb(summary.total_market_value_thb),
      description:
        summary?.total_market_value_thb == null
          ? "Waiting for authoritative price and FX data from a later backend PR."
          : "Authoritative backend market value.",
      unavailable: summary?.total_market_value_thb == null,
    }),
    [summary]
  );

  const positions = summary?.positions ?? [];
  const hasAllocationData = positions.some(
    (position) => numericValue(position.allocation_pct) != null
  );
  const attentionItems = useMemo<AttentionItem[]>(
    () => [
      {
        label: "Drafts require review",
        value: String(pendingDrafts.length),
        description:
          pendingDrafts.length === 0
            ? "No pending human review queue."
            : "Confirming a draft creates immutable ledger transactions.",
        tab: "drafts",
        urgent: pendingDrafts.length > 0,
      },
      {
        label: "Import rows blocked",
        value: String(importErrors.length),
        description:
          importErrors.length === 0
            ? "No current import diagnostics need review."
            : "Spreadsheet rows need correction before draft creation.",
        tab: "ledger",
        ledgerView: "import-errors",
        urgent: importErrors.length > 0,
      },
      {
        label: "Market pricing",
        value: summary?.total_market_value_thb == null ? "Unavailable" : "Available",
        description:
          summary?.total_market_value_thb == null
            ? "Market value, weights, unrealized P&L, and returns are intentionally omitted."
            : "Backend returned market value data.",
        urgent: false,
      },
    ],
    [importErrors.length, pendingDrafts.length, summary?.total_market_value_thb]
  );

  function openAttentionItem(item: AttentionItem) {
    if (!item.tab) return;
    setActiveTab(item.tab);
    if (item.ledgerView) setLedgerView(item.ledgerView);
  }

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

  async function handleUpdateDraft(
    draft: TransactionDraft,
    values: TransactionDraftMutation
  ) {
    try {
      setUpdatingDraftId(draft.id);
      setError(null);
      const updated = await updateTransactionDraft(draft.id, values);
      setNotice(`Updated draft ${updated.source_identifier ?? updated.id}.`);
      setEditingDraftId(null);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setUpdatingDraftId(null);
    }
  }

  async function handleCreateReversalDraft(transaction: ConfirmedTransaction) {
    try {
      setReversingTransactionId(transaction.id);
      setError(null);
      const draft = await createReversalDraft(transaction.id, {
        notes: `Review reversal for ${transaction.source_identifier ?? transaction.id}`,
      });
      setNotice(
        `Created reversal draft ${draft.source_identifier ?? draft.id}. Review it before confirming.`
      );
      await load();
      setActiveTab("drafts");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setReversingTransactionId(null);
    }
  }

  async function handleCreateCorrectionDraft(transaction: ConfirmedTransaction) {
    try {
      setCorrectingTransactionId(transaction.id);
      setError(null);
      const draft = await createCorrectionDraft(transaction.id, {
        notes: `Review correction for ${transaction.source_identifier ?? transaction.id}`,
      });
      setNotice(
        `Created correction draft ${draft.source_identifier ?? draft.id}. Edit it before confirming.`
      );
      await load();
      setEditingDraftId(draft.id);
      setActiveTab("drafts");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setCorrectingTransactionId(null);
    }
  }

  async function handleViewTransaction(transaction: ConfirmedTransaction) {
    try {
      setLoadingTransactionDetailId(transaction.id);
      setError(null);
      setSelectedTransaction(await fetchConfirmedTransaction(transaction.id));
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoadingTransactionDetailId(null);
    }
  }

  async function handleCreateAccount(values: {
    name: string;
    account_type: InvestmentAccountType;
    institution_name: string;
    external_identifier: string;
    currency: string;
  }) {
    try {
      setCreatingAccount(true);
      setError(null);
      const account = await createInvestmentAccount({
        name: values.name,
        account_type: values.account_type,
        institution_name: values.institution_name || null,
        external_identifier: values.external_identifier || null,
        currency: values.currency || "THB",
      });
      setNotice(`Created account ${account?.name ?? values.name}.`);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setCreatingAccount(false);
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
      <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 md:flex-row md:items-center md:justify-between">
        <div className="grid gap-2 md:grid-cols-5">
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

      {activeTab === "overview" && (
        <OverviewPanel
          summary={summary}
          positions={positions}
          metrics={overviewMetrics}
          marketValueMetric={marketValueMetric}
          attentionItems={attentionItems}
          hasAllocationData={hasAllocationData}
          onOpenAttentionItem={openAttentionItem}
          onOpenPositions={() => setActiveTab("positions")}
        />
      )}
      {activeTab === "positions" && (
        <PositionsPanel positions={positions} hasAllocationData={hasAllocationData} />
      )}
      {activeTab === "drafts" && (
        <DraftReviewPanel
          drafts={pendingDrafts}
          confirmingDraftId={confirmingDraftId}
          editingDraftId={editingDraftId}
          updatingDraftId={updatingDraftId}
          onEditDraft={(draft) => setEditingDraftId(draft.id)}
          onCancelEdit={() => setEditingDraftId(null)}
          onUpdateDraft={(draft, values) => void handleUpdateDraft(draft, values)}
          onConfirm={(draft) => void handleConfirm(draft)}
        />
      )}
      {activeTab === "activity" && (
        <ConfirmedTransactionsPanel
          transactions={confirmedTransactions}
          selectedTransaction={selectedTransaction}
          loadingTransactionDetailId={loadingTransactionDetailId}
          onViewTransaction={(transaction) => void handleViewTransaction(transaction)}
          onCloseDetail={() => setSelectedTransaction(null)}
          reversingTransactionId={reversingTransactionId}
          correctingTransactionId={correctingTransactionId}
          onCreateReversalDraft={(transaction) =>
            void handleCreateReversalDraft(transaction)
          }
          onCreateCorrectionDraft={(transaction) =>
            void handleCreateCorrectionDraft(transaction)
          }
        />
      )}
      {activeTab === "ledger" && (
        <LedgerPanel
          activeView={ledgerView}
          onChangeView={setLedgerView}
          summary={summary}
          accounts={accounts}
          creatingAccount={creatingAccount}
          onCreateAccount={(values) => void handleCreateAccount(values)}
          importBatches={importBatches}
          importErrors={importErrors}
        />
      )}
    </div>
  );
}

function OverviewPanel({
  summary,
  positions,
  metrics,
  marketValueMetric,
  attentionItems,
  hasAllocationData,
  onOpenAttentionItem,
  onOpenPositions,
}: {
  summary: LedgerSummary | null;
  positions: LedgerSummary["positions"];
  metrics: OverviewMetric[];
  marketValueMetric: OverviewMetric;
  attentionItems: AttentionItem[];
  hasAllocationData: boolean;
  onOpenAttentionItem: (item: AttentionItem) => void;
  onOpenPositions: () => void;
}) {
  const visiblePositions = positions.slice(0, 6);
  const asOfLabel = summary?.as_of_transaction_at
    ? formatDate(summary.as_of_transaction_at)
    : "No confirmed transactions";

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-5">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="overflow-hidden">
          <div className="flex flex-col gap-3 border-b px-5 py-4 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="font-semibold">What you own</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                {positions.length} ledger-derived positions as of {asOfLabel}.
              </p>
            </div>
            <Button size="sm" variant="outline" onClick={onOpenPositions}>
              <Eye className="h-4 w-4" />
              Positions
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  {["Asset", "Account", "Quantity", "Cost basis", "Realized P&L"].map(
                    (heading) => (
                      <th key={heading} className="px-4 py-3 font-medium">
                        {heading}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y">
                {visiblePositions.length === 0 && (
                  <tr>
                    <td colSpan={5} className="h-36 px-6 text-center text-muted-foreground">
                      No confirmed positions yet.
                    </td>
                  </tr>
                )}
                {visiblePositions.map((position) => (
                  <tr
                    key={`${position.investment_account_id}-${position.asset_id}`}
                    className="hover:bg-muted/30"
                  >
                    <td className="px-4 py-4">
                      <p className="font-semibold">{position.asset_symbol ?? "-"}</p>
                      <p className="text-xs text-muted-foreground">
                        {position.asset_type ?? "Asset"} - {position.asset_currency ?? "-"}
                      </p>
                    </td>
                    <td className="px-4 py-4 font-medium">
                      {position.investment_account_name ?? "Unknown account"}
                    </td>
                    <td className="px-4 py-4 tabular-nums">
                      {formatDecimal(position.quantity, 8)}
                    </td>
                    <td className="px-4 py-4 tabular-nums">
                      {formatThb(position.cost_basis_thb)}
                    </td>
                    <td className="px-4 py-4 tabular-nums">
                      {formatThb(position.realized_pnl_thb)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-4">
          <MetricCard metric={marketValueMetric} />
          <Card>
            <CardHeader className="p-5 pb-3">
              <CardTitle className="text-base">Needs attention</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 p-5 pt-0">
              {attentionItems.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => onOpenAttentionItem(item)}
                  disabled={!item.tab}
                  className={cn(
                    "w-full rounded-lg border p-3 text-left transition-colors",
                    item.urgent
                      ? "border-primary/30 bg-primary/5"
                      : "border-border bg-background",
                    item.tab && "hover:bg-muted"
                  )}
                >
                  <span className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{item.label}</span>
                    <span className="text-sm font-semibold tabular-nums">{item.value}</span>
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                    {item.description}
                  </span>
                </button>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <AllocationPanel positions={positions} hasAllocationData={hasAllocationData} />
    </div>
  );
}

function MetricCard({ metric }: { metric: OverviewMetric }) {
  return (
    <Card className={cn(metric.unavailable && "border-dashed")}>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {metric.label}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <p
          className={cn(
            "text-xl font-semibold tabular-nums",
            metric.unavailable && "text-muted-foreground"
          )}
        >
          {metric.value}
        </p>
        <p className="mt-2 text-xs leading-5 text-muted-foreground">
          {metric.description}
        </p>
      </CardContent>
    </Card>
  );
}

function AllocationPanel({
  positions,
  hasAllocationData,
}: {
  positions: LedgerSummary["positions"];
  hasAllocationData: boolean;
}) {
  if (!hasAllocationData) {
    return (
      <Card className="border-dashed">
        <CardContent className="p-5">
          <h2 className="font-semibold">Allocation unavailable</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Portfolio weights are hidden until the backend returns authoritative
            allocation values from price and FX data.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">Allocation</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Displaying backend-provided allocation percentages only.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              {["Asset", "Account", "Allocation", "Market value"].map((heading) => (
                <th key={heading} className="px-4 py-3 font-medium">
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {positions.map((position) => (
              <tr
                key={`${position.investment_account_id}-${position.asset_id}`}
                className="hover:bg-muted/30"
              >
                <td className="px-4 py-4 font-semibold">{position.asset_symbol ?? "-"}</td>
                <td className="px-4 py-4">
                  {position.investment_account_name ?? "Unknown account"}
                </td>
                <td className="px-4 py-4 tabular-nums">
                  {formatPercent(position.allocation_pct)}
                </td>
                <td className="px-4 py-4 tabular-nums">
                  {formatThb(position.market_value_thb)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function PositionsPanel({
  positions,
  hasAllocationData,
}: {
  positions: LedgerSummary["positions"];
  hasAllocationData: boolean;
}) {
  return (
    <div className="space-y-4">
      {!hasAllocationData && (
        <Card className="border-dashed">
          <CardContent className="p-4 text-sm text-muted-foreground">
            Market value, weight, unrealized P&L, and returns are intentionally
            omitted until the backend supplies authoritative price and FX data.
          </CardContent>
        </Card>
      )}
      <Card className="overflow-hidden">
        <div className="border-b px-5 py-4">
          <h2 className="font-semibold">Positions</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Simplified view of ledger-derived ownership and cost basis.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                {["Asset", "Account", "Quantity", "Cost basis", "Average cost", "Realized P&L"].map(
                  (heading) => (
                    <th key={heading} className="px-4 py-3 font-medium">
                      {heading}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y">
              {positions.length === 0 && (
                <tr>
                  <td colSpan={6} className="h-40 px-6 text-center text-muted-foreground">
                    No confirmed ledger positions yet.
                  </td>
                </tr>
              )}
              {positions.map((position) => (
                <tr
                  key={`${position.investment_account_id}-${position.asset_id}`}
                  className="hover:bg-muted/30"
                >
                  <td className="px-4 py-4">
                    <p className="font-semibold">{position.asset_symbol ?? "-"}</p>
                    <p className="text-xs text-muted-foreground">
                      {position.asset_type ?? "Asset"} - {position.asset_currency ?? "-"}
                    </p>
                  </td>
                  <td className="px-4 py-4 font-medium">
                    {position.investment_account_name ?? "Unknown account"}
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function LedgerPanel({
  activeView,
  onChangeView,
  summary,
  accounts,
  creatingAccount,
  onCreateAccount,
  importBatches,
  importErrors,
}: {
  activeView: LedgerView;
  onChangeView: (view: LedgerView) => void;
  summary: LedgerSummary | null;
  accounts: InvestmentAccount[];
  creatingAccount: boolean;
  onCreateAccount: (values: {
    name: string;
    account_type: InvestmentAccountType;
    institution_name: string;
    external_identifier: string;
    currency: string;
  }) => void;
  importBatches: TransactionImportBatch[];
  importErrors: TransactionImportError[];
}) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 rounded-xl border bg-card p-2">
        {ledgerViews.map((view) => {
          const active = activeView === view.id;
          return (
            <button
              key={view.id}
              type="button"
              onClick={() => onChangeView(view.id)}
              className={cn(
                "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              {view.label}
            </button>
          );
        })}
      </div>

      {activeView === "summary" && <LedgerSummaryPanel summary={summary} />}
      {activeView === "accounts" && (
        <InvestmentAccountsPanel
          accounts={accounts}
          creating={creatingAccount}
          onCreate={onCreateAccount}
        />
      )}
      {activeView === "import-errors" && (
        <ImportErrorsPanel batches={importBatches} errors={importErrors} />
      )}
      {activeView === "legacy" && (
        <div className="space-y-3">
          <div className="rounded-xl border bg-card px-5 py-4">
            <h2 className="font-semibold">Legacy holdings archive</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Migration-era paper holdings from approved analyses. This is not the
              current ledger source of truth.
            </p>
          </div>
          <PortfolioList />
        </div>
      )}
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
                  <p className="font-semibold">{position.asset_symbol ?? "-"}</p>
                  <p className="text-xs text-muted-foreground">
                    {position.asset_type ?? "Asset"} - {position.asset_currency ?? "-"}
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

function InvestmentAccountsPanel({
  accounts,
  creating,
  onCreate,
}: {
  accounts: InvestmentAccount[];
  creating: boolean;
  onCreate: (values: {
    name: string;
    account_type: InvestmentAccountType;
    institution_name: string;
    external_identifier: string;
    currency: string;
  }) => void;
}) {
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState<InvestmentAccountType>("BROKERAGE");
  const [institutionName, setInstitutionName] = useState("");
  const [externalIdentifier, setExternalIdentifier] = useState("");
  const [currency, setCurrency] = useState("THB");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const accountName = name.trim();
    if (!accountName) return;
    onCreate({
      name: accountName,
      account_type: accountType,
      institution_name: institutionName.trim(),
      external_identifier: externalIdentifier.trim(),
      currency: currency.trim().toUpperCase() || "THB",
    });
    setName("");
    setInstitutionName("");
    setExternalIdentifier("");
    setCurrency("THB");
    setAccountType("BROKERAGE");
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
      <Card>
        <CardHeader className="p-5 pb-3">
          <CardTitle className="text-base">Add account</CardTitle>
        </CardHeader>
        <CardContent className="p-5 pt-0">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <label className="block text-sm font-medium">
              Account name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Me - InnovestX"
                className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
                maxLength={120}
                required
              />
            </label>
            <label className="block text-sm font-medium">
              Type
              <select
                value={accountType}
                onChange={(event) =>
                  setAccountType(event.target.value as InvestmentAccountType)
                }
                className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
              >
                {accountTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium">
              Institution
              <input
                value={institutionName}
                onChange={(event) => setInstitutionName(event.target.value)}
                placeholder="Broker, bank, exchange"
                className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
                maxLength={120}
              />
            </label>
            <label className="block text-sm font-medium">
              Reference
              <input
                value={externalIdentifier}
                onChange={(event) => setExternalIdentifier(event.target.value)}
                placeholder="Optional nickname or account suffix"
                className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
                maxLength={120}
              />
            </label>
            <label className="block text-sm font-medium">
              Currency
              <input
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
                className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm uppercase outline-none focus:border-primary"
                minLength={3}
                maxLength={10}
                required
              />
            </label>
            <Button type="submit" disabled={creating || !name.trim()} className="w-full">
              {creating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Add account
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card className="overflow-hidden">
        <div className="border-b px-5 py-4">
          <h2 className="font-semibold">Investment accounts</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Use separate accounts for your own, spouse, parent, broker, bank, and wallet records.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                {["Name", "Type", "Institution", "Reference", "Currency", "Created"].map(
                  (heading) => (
                    <th key={heading} className="px-4 py-3 font-medium">
                      {heading}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y">
              {accounts.length === 0 && (
                <tr>
                  <td colSpan={6} className="h-40 px-6 text-center text-muted-foreground">
                    No investment accounts yet.
                  </td>
                </tr>
              )}
              {accounts.map((account) => (
                <tr key={account.id} className="hover:bg-muted/30">
                  <td className="px-4 py-4 font-medium">{account.name}</td>
                  <td className="px-4 py-4">
                    <Badge variant="secondary">
                      {accountTypeOptions.find((option) => option.value === account.account_type)
                        ?.label ?? account.account_type}
                    </Badge>
                  </td>
                  <td className="px-4 py-4">{account.institution_name ?? "-"}</td>
                  <td className="px-4 py-4">{account.external_identifier ?? "-"}</td>
                  <td className="px-4 py-4 tabular-nums">{account.currency}</td>
                  <td className="px-4 py-4 tabular-nums">{formatDate(account.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function DraftReviewPanel({
  drafts,
  confirmingDraftId,
  editingDraftId,
  updatingDraftId,
  onEditDraft,
  onCancelEdit,
  onUpdateDraft,
  onConfirm,
}: {
  drafts: TransactionDraft[];
  confirmingDraftId: string | null;
  editingDraftId: string | null;
  updatingDraftId: string | null;
  onEditDraft: (draft: TransactionDraft) => void;
  onCancelEdit: () => void;
  onUpdateDraft: (draft: TransactionDraft, values: TransactionDraftMutation) => void;
  onConfirm: (draft: TransactionDraft) => void;
}) {
  const editingDraft = drafts.find((draft) => draft.id === editingDraftId) ?? null;

  return (
    <Card className="overflow-hidden">
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">Pending transaction drafts</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Confirming creates immutable ledger transactions. Corrections require linked
          reversals.
        </p>
      </div>
      {editingDraft && (
        <DraftEditPanel
          key={editingDraft.id}
          draft={editingDraft}
          updating={updatingDraftId === editingDraft.id}
          onCancel={onCancelEdit}
          onSave={(values) => onUpdateDraft(editingDraft, values)}
        />
      )}
      <DraftTable
        drafts={drafts}
        emptyMessage="No pending drafts. Imported rows have already been confirmed."
        action={(draft) => (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => onEditDraft(draft)}
              disabled={updatingDraftId === draft.id}
            >
              <Pencil className="h-4 w-4" />
              Edit
            </Button>
            <Button
              size="sm"
              onClick={() => onConfirm(draft)}
              disabled={confirmingDraftId === draft.id || updatingDraftId === draft.id}
            >
              {confirmingDraftId === draft.id ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              Confirm
            </Button>
          </div>
        )}
      />
    </Card>
  );
}

function DraftEditPanel({
  draft,
  updating,
  onCancel,
  onSave,
}: {
  draft: TransactionDraft;
  updating: boolean;
  onCancel: () => void;
  onSave: (values: TransactionDraftMutation) => void;
}) {
  const [transactionAt, setTransactionAt] = useState(
    formatDateTimeInput(draft.transaction_at)
  );
  const [quantity, setQuantity] = useState(inputValue(draft.quantity));
  const [unitPrice, setUnitPrice] = useState(inputValue(draft.unit_price));
  const [grossAmount, setGrossAmount] = useState(inputValue(draft.gross_amount));
  const [feeAmount, setFeeAmount] = useState(inputValue(draft.fee_amount));
  const [feeUnit, setFeeUnit] = useState(draft.fee_unit ?? "");
  const [currency, setCurrency] = useState(draft.currency);
  const [fxRate, setFxRate] = useState(inputValue(draft.fx_rate_to_thb));
  const [sourceIdentifier, setSourceIdentifier] = useState(
    draft.source_identifier ?? ""
  );
  const [sourceRowNumber, setSourceRowNumber] = useState(
    draft.source_row_number == null ? "" : String(draft.source_row_number)
  );
  const [notes, setNotes] = useState(draft.notes ?? "");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave({
      transaction_at: new Date(transactionAt).toISOString(),
      quantity: nullableString(quantity),
      unit_price: nullableString(unitPrice),
      gross_amount: nullableString(grossAmount),
      fee_amount: nullableString(feeAmount),
      fee_unit: feeUnit === "" ? null : (feeUnit as "QUOTE_CURRENCY" | "ASSET_UNITS"),
      currency: currency.trim().toUpperCase(),
      fx_rate_to_thb: nullableString(fxRate),
      source_identifier: nullableString(sourceIdentifier),
      source_row_number: sourceRowNumber.trim()
        ? Number(sourceRowNumber)
        : null,
      notes: nullableString(notes),
    });
  }

  return (
    <div className="border-b bg-muted/20 px-5 py-4">
      <div className="mb-4">
        <h3 className="font-semibold">Edit pending draft</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          {draft.assets?.symbol ?? "Asset"} {draft.transaction_type} -{" "}
          {draft.investment_accounts?.name ?? "Unknown account"}
        </p>
      </div>
      <form className="grid gap-3 md:grid-cols-4" onSubmit={handleSubmit}>
        <label className="block text-sm font-medium">
          Date
          <input
            type="datetime-local"
            value={transactionAt}
            onChange={(event) => setTransactionAt(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
            required
          />
        </label>
        <DraftNumberInput label="Quantity" value={quantity} onChange={setQuantity} />
        <DraftNumberInput label="Unit price" value={unitPrice} onChange={setUnitPrice} />
        <DraftNumberInput label="Gross amount" value={grossAmount} onChange={setGrossAmount} />
        <DraftNumberInput label="Fee amount" value={feeAmount} onChange={setFeeAmount} />
        <label className="block text-sm font-medium">
          Fee unit
          <select
            value={feeUnit}
            onChange={(event) => setFeeUnit(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
          >
            <option value="">None</option>
            <option value="QUOTE_CURRENCY">Quote currency</option>
            <option value="ASSET_UNITS">Asset units</option>
          </select>
        </label>
        <label className="block text-sm font-medium">
          Currency
          <input
            value={currency}
            onChange={(event) => setCurrency(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm uppercase outline-none focus:border-primary"
            minLength={3}
            maxLength={10}
            required
          />
        </label>
        <DraftNumberInput label="FX to THB" value={fxRate} onChange={setFxRate} />
        <label className="block text-sm font-medium md:col-span-2">
          Source
          <input
            value={sourceIdentifier}
            onChange={(event) => setSourceIdentifier(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
            maxLength={200}
          />
        </label>
        <label className="block text-sm font-medium">
          Row
          <input
            type="number"
            min={1}
            value={sourceRowNumber}
            onChange={(event) => setSourceRowNumber(event.target.value)}
            className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
          />
        </label>
        <label className="block text-sm font-medium md:col-span-4">
          Notes
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className="mt-1 min-h-20 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            maxLength={500}
          />
        </label>
        <div className="flex gap-2 md:col-span-4">
          <Button type="submit" disabled={updating || !transactionAt || !currency.trim()}>
            {updating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save draft
          </Button>
          <Button type="button" variant="outline" onClick={onCancel} disabled={updating}>
            <X className="h-4 w-4" />
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}

function DraftNumberInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        type="number"
        step="any"
        min={0}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary"
      />
    </label>
  );
}

function ConfirmedTransactionsPanel({
  transactions,
  selectedTransaction,
  loadingTransactionDetailId,
  onViewTransaction,
  onCloseDetail,
  reversingTransactionId,
  correctingTransactionId,
  onCreateReversalDraft,
  onCreateCorrectionDraft,
}: {
  transactions: ConfirmedTransaction[];
  selectedTransaction: ConfirmedTransaction | null;
  loadingTransactionDetailId: string | null;
  onViewTransaction: (transaction: ConfirmedTransaction) => void;
  onCloseDetail: () => void;
  reversingTransactionId: string | null;
  correctingTransactionId: string | null;
  onCreateReversalDraft: (transaction: ConfirmedTransaction) => void;
  onCreateCorrectionDraft: (transaction: ConfirmedTransaction) => void;
}) {
  const reversedTransactionIds = useMemo(
    () =>
      new Set(
        transactions
          .map((transaction) => transaction.reversal_of_transaction_id)
          .filter((id): id is string => Boolean(id))
      ),
    [transactions]
  );

  return (
    <Card className="overflow-hidden">
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">Confirmed transactions</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Immutable ledger rows sorted by transaction date and ledger sequence.
        </p>
      </div>
      {(selectedTransaction || loadingTransactionDetailId) && (
        <TransactionDetailPanel
          transaction={selectedTransaction}
          loading={Boolean(loadingTransactionDetailId)}
          onClose={onCloseDetail}
          onCreateReversalDraft={onCreateReversalDraft}
          onCreateCorrectionDraft={onCreateCorrectionDraft}
          reversingTransactionId={reversingTransactionId}
          correctingTransactionId={correctingTransactionId}
        />
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1180px] text-left text-sm">
          <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              {[
                "Date",
                "Sequence",
                "Account",
                "Asset",
                "Type",
                "Quantity",
                "Price",
                "Gross",
                "Fee",
                "FX",
                "Source",
                "Draft",
                "Action",
              ].map((heading) => (
                <th key={heading} className="px-4 py-3 font-medium">
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {transactions.length === 0 && (
              <tr>
                <td colSpan={13} className="h-40 px-6 text-center text-muted-foreground">
                  No confirmed transactions yet.
                </td>
              </tr>
            )}
            {transactions.map((transaction) => {
              const cannotReverse =
                transaction.transaction_type === "REVERSAL" ||
                reversedTransactionIds.has(transaction.id);
              const isReversing = reversingTransactionId === transaction.id;
              const isCorrecting = correctingTransactionId === transaction.id;
              return (
                <tr key={transaction.id} className="align-top hover:bg-muted/30">
                  <td className="px-4 py-4 tabular-nums">
                    {formatDate(transaction.transaction_at)}
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {transaction.ledger_sequence}
                  </td>
                  <td className="px-4 py-4">
                    {transaction.investment_accounts?.name ?? "Unknown account"}
                  </td>
                  <td className="px-4 py-4">
                    <p className="font-semibold">{transaction.assets?.symbol ?? "-"}</p>
                    <p className="text-xs text-muted-foreground">
                      {transaction.assets?.asset_type ?? "Asset"} -{" "}
                      {transaction.assets?.currency ?? transaction.currency}
                    </p>
                  </td>
                  <td className="px-4 py-4">
                    <Badge variant="secondary">{transaction.transaction_type}</Badge>
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {formatDecimal(transaction.quantity, 8)}
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {formatDecimal(transaction.unit_price, 8)} {transaction.currency}
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {formatDecimal(transaction.gross_amount, 8)} {transaction.currency}
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {formatDecimal(transaction.fee_amount, 8)}
                    <p className="text-xs text-muted-foreground">
                      {transaction.fee_unit ?? "-"}
                    </p>
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {formatDecimal(transaction.fx_rate_to_thb, 6)}
                  </td>
                  <td className="px-4 py-4">
                    <p className="font-medium">
                      {transaction.source_identifier ?? transaction.source_type}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Row {transaction.source_row_number ?? "-"}
                    </p>
                  </td>
                  <td className="px-4 py-4">
                    {transaction.confirmed_from_draft_id ? (
                      <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                        {transaction.confirmed_from_draft_id.slice(0, 8)}
                      </code>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onViewTransaction(transaction)}
                        disabled={loadingTransactionDetailId === transaction.id}
                      >
                        {loadingTransactionDetailId === transaction.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                        View
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onCreateCorrectionDraft(transaction)}
                        disabled={isCorrecting}
                      >
                        {isCorrecting ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Pencil className="h-4 w-4" />
                        )}
                        Correct
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onCreateReversalDraft(transaction)}
                        disabled={cannotReverse || isReversing}
                      >
                        {isReversing ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RotateCcw className="h-4 w-4" />
                        )}
                        Reverse
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function TransactionDetailPanel({
  transaction,
  loading,
  onClose,
  onCreateReversalDraft,
  onCreateCorrectionDraft,
  reversingTransactionId,
  correctingTransactionId,
}: {
  transaction: ConfirmedTransaction | null;
  loading: boolean;
  onClose: () => void;
  onCreateReversalDraft: (transaction: ConfirmedTransaction) => void;
  onCreateCorrectionDraft: (transaction: ConfirmedTransaction) => void;
  reversingTransactionId: string | null;
  correctingTransactionId: string | null;
}) {
  if (loading && transaction == null) {
    return (
      <div className="border-b px-5 py-6 text-sm text-muted-foreground">
        <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
        Loading transaction detail...
      </div>
    );
  }
  if (transaction == null) return null;

  const cannotReverse =
    transaction.transaction_type === "REVERSAL" ||
    Boolean(transaction.reversal_of_transaction_id);
  const isReversing = reversingTransactionId === transaction.id;
  const isCorrecting = correctingTransactionId === transaction.id;

  return (
    <div className="border-b bg-muted/20 px-5 py-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h3 className="font-semibold">
            {transaction.assets?.symbol ?? "Asset"} {transaction.transaction_type}
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {transaction.investment_accounts?.name ?? "Unknown account"} -{" "}
            {formatDate(transaction.transaction_at)} - sequence{" "}
            {transaction.ledger_sequence}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onCreateCorrectionDraft(transaction)}
            disabled={isCorrecting}
          >
            {isCorrecting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Pencil className="h-4 w-4" />
            )}
            Correct
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onCreateReversalDraft(transaction)}
            disabled={cannotReverse || isReversing}
          >
            {isReversing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RotateCcw className="h-4 w-4" />
            )}
            Reverse
          </Button>
          <Button size="sm" variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>

      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-4">
        <DetailItem label="Quantity" value={formatDecimal(transaction.quantity, 8)} />
        <DetailItem
          label="Unit price"
          value={`${formatDecimal(transaction.unit_price, 8)} ${transaction.currency}`}
        />
        <DetailItem
          label="Gross"
          value={`${formatDecimal(transaction.gross_amount, 8)} ${transaction.currency}`}
        />
        <DetailItem label="FX to THB" value={formatDecimal(transaction.fx_rate_to_thb, 6)} />
        <DetailItem label="Fee" value={formatDecimal(transaction.fee_amount, 8)} />
        <DetailItem label="Fee unit" value={transaction.fee_unit ?? "-"} />
        <DetailItem label="Source" value={transaction.source_identifier ?? transaction.source_type} />
        <DetailItem
          label="Confirmed draft"
          value={transaction.confirmed_from_draft_id?.slice(0, 8) ?? "-"}
        />
      </dl>
      {transaction.notes && (
        <p className="mt-4 text-sm text-muted-foreground">{transaction.notes}</p>
      )}
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function ImportErrorsPanel({
  batches,
  errors,
}: {
  batches: TransactionImportBatch[];
  errors: TransactionImportError[];
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
      <Card className="overflow-hidden">
        <div className="border-b px-5 py-4">
          <h2 className="font-semibold">Recent import batches</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                {["File", "Status", "Created"].map((heading) => (
                  <th key={heading} className="px-4 py-3 font-medium">
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {batches.length === 0 && (
                <tr>
                  <td colSpan={3} className="h-32 px-6 text-center text-muted-foreground">
                    No import batches yet.
                  </td>
                </tr>
              )}
              {batches.map((batch) => (
                <tr key={batch.id} className="hover:bg-muted/30">
                  <td className="px-4 py-4">
                    <p className="font-medium">{batch.source_filename ?? batch.source_type}</p>
                    <p className="text-xs text-muted-foreground">
                      {batch.source_identifier ?? "-"}
                    </p>
                  </td>
                  <td className="px-4 py-4">
                    <Badge variant="secondary">{batch.status}</Badge>
                  </td>
                  <td className="px-4 py-4 tabular-nums">{formatDate(batch.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="border-b px-5 py-4">
          <h2 className="font-semibold">Blocked rows</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[940px] text-left text-sm">
            <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                {[
                  "Created",
                  "File",
                  "Source",
                  "Row",
                  "Code",
                  "Message",
                  "Details",
                ].map((heading) => (
                  <th key={heading} className="px-4 py-3 font-medium">
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {errors.length === 0 && (
                <tr>
                  <td colSpan={7} className="h-40 px-6 text-center text-muted-foreground">
                    No blocked import rows.
                  </td>
                </tr>
              )}
              {errors.map((error) => (
                <tr key={error.id} className="align-top hover:bg-muted/30">
                  <td className="px-4 py-4 tabular-nums">{formatDate(error.created_at)}</td>
                  <td className="px-4 py-4">
                    {error.transaction_import_batches?.source_filename ?? "-"}
                  </td>
                  <td className="px-4 py-4">
                    {error.source_identifier ?? error.import_batch_id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {error.source_row_number ?? "-"}
                  </td>
                  <td className="px-4 py-4">
                    <Badge variant="secondary">{error.error_code}</Badge>
                  </td>
                  <td className="px-4 py-4">{error.error_message}</td>
                  <td className="px-4 py-4">
                    <pre className="max-w-[280px] overflow-auto rounded bg-muted p-2 text-xs">
                      {formatJson(error.error_details)}
                    </pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function formatJson(value: Record<string, unknown>) {
  const text = JSON.stringify(value, null, 2);
  return text === "{}" ? "-" : text;
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
                <p className="font-medium">{draft.source_identifier ?? "-"}</p>
                <p className="text-xs text-muted-foreground">
                  Row {draft.source_row_number ?? "-"} - {draft.source_type}
                </p>
              </td>
              <td className="px-4 py-4">
                {draft.investment_accounts?.name ?? "Unknown account"}
              </td>
              <td className="px-4 py-4">
                <p className="font-semibold">{draft.assets?.symbol ?? "-"}</p>
                <p className="text-xs text-muted-foreground">
                  {draft.assets?.asset_type ?? "Asset"} - {draft.assets?.currency ?? draft.currency}
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
                <p className="text-xs text-muted-foreground">{draft.fee_unit ?? "-"}</p>
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
                  "-"
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
