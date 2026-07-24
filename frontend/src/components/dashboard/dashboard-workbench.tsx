"use client";

import {
  ArrowRight,
  BarChart3,
  BriefcaseBusiness,
  CheckCircle2,
  Inbox,
  Loader2,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ApiError,
  fetchInbox,
  fetchLatestScreeningRun,
  fetchPortfolio,
  type InboxItem,
  type PortfolioHolding,
  type ScreeningRun,
} from "@/lib/api";

function errorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return "Your session could not be verified. Sign in again to load workspace data.";
  }
  return error instanceof Error ? error.message : "Workspace data could not be loaded.";
}

function displayLabel(value: string | null | undefined) {
  if (!value) return "—";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function formatMoney(value: number | null | undefined) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function recommendationClass(value: string | null) {
  switch (value?.toUpperCase()) {
    case "BUY":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700";
    case "HOLD":
      return "border-amber-500/30 bg-amber-500/10 text-amber-700";
    case "SELL":
    case "PASS":
      return "border-rose-500/30 bg-rose-500/10 text-rose-700";
    default:
      return "";
  }
}

export function DashboardWorkbench() {
  const [pending, setPending] = useState<InboxItem[]>([]);
  const [approved, setApproved] = useState<InboxItem[]>([]);
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([]);
  const [latestRun, setLatestRun] = useState<ScreeningRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pendingItems, approvedItems, portfolioItems, screeningRun] =
        await Promise.all([
          fetchInbox("pending_review"),
          fetchInbox("approved"),
          fetchPortfolio(),
          fetchLatestScreeningRun(),
        ]);
      setPending(pendingItems);
      setApproved(approvedItems);
      setHoldings(portfolioItems);
      setLatestRun(screeningRun);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const recentAnalysis = useMemo(
    () =>
      [...pending, ...approved]
        .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
        .slice(0, 5),
    [approved, pending]
  );

  const portfolioCostBasis = useMemo(
    () =>
      holdings.reduce(
        (total, holding) => total + (holding.cost_basis == null ? 0 : Number(holding.cost_basis)),
        0
      ),
    [holdings]
  );

  const metrics = [
    {
      label: "Pending Review",
      value: error ? "—" : String(pending.length),
      detail: error
        ? "Data unavailable"
        : pending.length === 1
          ? "idea needs a decision"
          : "ideas need a decision",
      href: "/inbox",
      icon: Inbox,
    },
    {
      label: "Approved Ideas",
      value: error ? "—" : String(approved.length),
      detail: error ? "Data unavailable" : "approved research records",
      href: "/inbox",
      icon: CheckCircle2,
    },
    {
      label: "Active Holdings",
      value: error ? "—" : String(holdings.length),
      detail: error ? "Data unavailable" : "paper portfolio positions",
      href: "/portfolio",
      icon: BriefcaseBusiness,
    },
    {
      label: "Recent Screening Runs",
      value: error ? "—" : latestRun ? displayLabel(latestRun.status) : "—",
      detail: error
        ? "Data unavailable"
        : latestRun
          ? `Latest run ${formatDate(latestRun.started_at)}`
          : "No screening runs yet",
      href: "/screener",
      icon: BarChart3,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investment workflow"
        title="Dashboard"
        description="Monitor research moving from quantitative screening through analyst review and into the paper portfolio."
        actions={
          <Button asChild size="sm">
            <Link href="/inbox">
              Review analysis
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        }
      />

      {error && (
        <div className="flex flex-col gap-3 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
          <p>{error}</p>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      )}

      <section aria-label="Workflow summary">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => (
            <Card key={metric.label} className="shadow-none">
              <Link
                href={metric.href}
                className="block rounded-lg transition-colors hover:bg-muted/30"
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-xs font-medium text-muted-foreground">{metric.label}</p>
                    <metric.icon className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="mt-3 flex items-end justify-between gap-3">
                    {loading ? (
                      <Loader2 className="mb-1 h-5 w-5 animate-spin text-muted-foreground" />
                    ) : (
                      <p className="text-2xl font-semibold tracking-tight">{metric.value}</p>
                    )}
                    <p className="truncate text-right text-[11px] text-muted-foreground">
                      {metric.detail}
                    </p>
                  </div>
                </CardContent>
              </Link>
            </Card>
          ))}
        </div>
      </section>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.85fr)]">
        <Card className="overflow-hidden shadow-none">
          <div className="flex items-center justify-between border-b px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold">Recent Analysis</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Latest research produced for human review
              </p>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/inbox">
                View inbox
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>

          {loading ? (
            <div className="flex h-52 items-center justify-center text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading recent analysis
            </div>
          ) : error ? (
            <div className="flex h-52 flex-col items-center justify-center px-6 text-center">
              <p className="text-sm font-medium">Analysis data unavailable</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Retry the workspace request above.
              </p>
            </div>
          ) : recentAnalysis.length === 0 ? (
            <div className="flex h-52 flex-col items-center justify-center px-6 text-center">
              <Inbox className="h-5 w-5 text-muted-foreground" />
              <p className="mt-3 text-sm font-medium">No analysis available</p>
              <p className="mt-1 max-w-sm text-xs leading-5 text-muted-foreground">
                Completed AI research will appear here after a screening run selects candidates.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="border-b bg-muted/35 text-xs text-muted-foreground">
                  <tr>
                    {["Company", "Recommendation", "Fair Value", "Status", "Created"].map(
                      (heading) => (
                        <th key={heading} className="px-4 py-2.5 font-medium">
                          {heading}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {recentAnalysis.map((item) => (
                    <tr key={item.id} className="hover:bg-muted/25">
                      <td className="px-4 py-3">
                        <p className="font-semibold">{item.tickers?.symbol ?? "—"}</p>
                        <p className="max-w-44 truncate text-xs text-muted-foreground">
                          {item.tickers?.name ?? "Unknown company"}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          variant="outline"
                          className={recommendationClass(item.recommendation)}
                        >
                          {displayLabel(item.recommendation)}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 font-medium tabular-nums">
                        {formatMoney(item.fair_value)}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {displayLabel(item.status)}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDate(item.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="overflow-hidden shadow-none">
          <div className="flex items-center justify-between border-b px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold">Portfolio Snapshot</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">Active paper holdings</p>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/portfolio">
                Open
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>

          {loading ? (
            <div className="flex h-52 items-center justify-center text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading portfolio
            </div>
          ) : error ? (
            <div className="flex h-52 flex-col items-center justify-center px-6 text-center">
              <p className="text-sm font-medium">Portfolio data unavailable</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Retry the workspace request above.
              </p>
            </div>
          ) : holdings.length === 0 ? (
            <div className="flex h-52 flex-col items-center justify-center px-6 text-center">
              <BriefcaseBusiness className="h-5 w-5 text-muted-foreground" />
              <p className="mt-3 text-sm font-medium">No active holdings</p>
              <p className="mt-1 max-w-xs text-xs leading-5 text-muted-foreground">
                Approved ideas can be added as paper positions from the analysis inbox.
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 border-b">
                <div className="p-4">
                  <p className="text-xs text-muted-foreground">Positions</p>
                  <p className="mt-1 text-xl font-semibold">{holdings.length}</p>
                </div>
                <div className="border-l p-4">
                  <p className="text-xs text-muted-foreground">Recorded cost basis</p>
                  <p className="mt-1 text-xl font-semibold">
                    {portfolioCostBasis > 0 ? formatMoney(portfolioCostBasis) : "—"}
                  </p>
                </div>
              </div>
              <div className="divide-y">
                {holdings.slice(0, 5).map((holding) => (
                  <div
                    key={holding.id}
                    className="flex items-center justify-between gap-4 px-5 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-semibold">
                        {holding.tickers?.symbol ?? "—"}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {holding.tickers?.name ?? "Unknown company"}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium tabular-nums">{holding.shares}</p>
                      <p className="text-xs text-muted-foreground">shares</p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
