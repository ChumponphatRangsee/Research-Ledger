"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ApiError,
  fetchInbox,
  fetchPortfolio,
  type InboxItem,
  type PortfolioHolding,
} from "@/lib/api";

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return "Please sign in again to view your portfolio.";
  }
  if (error instanceof Error) return error.message;
  return "Could not load portfolio.";
}

function formatMoney(value: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatShares(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 6,
  }).format(Number(value));
}

type HoldingMetrics = {
  holding: PortfolioHolding;
  priceSnapshot: number | null;
  marketValue: number | null;
  effectiveCostBasis: number | null;
  gainLoss: number | null;
  gainLossPct: number | null;
  allocationPct: number | null;
};

function gainLossClass(value: number | null) {
  if (value == null || value === 0) return "text-muted-foreground";
  return value > 0
    ? "text-emerald-700 dark:text-emerald-400"
    : "text-rose-700 dark:text-rose-400";
}

export function PortfolioList() {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([]);
  const [analysisById, setAnalysisById] = useState<Record<string, InboxItem>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [portfolioData, approvedAnalyses] = await Promise.all([
        fetchPortfolio(),
        fetchInbox("approved"),
      ]);
      setHoldings(portfolioData);
      setAnalysisById(
        Object.fromEntries(approvedAnalyses.map((analysis) => [analysis.id, analysis]))
      );
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const metrics = useMemo<HoldingMetrics[]>(() => {
    const base = holdings.map((holding) => {
      const analysis = holding.approved_from_inbox_id
        ? analysisById[holding.approved_from_inbox_id]
        : undefined;
      const shares = Number(holding.shares);
      const priceSnapshot =
        analysis?.current_price == null ? null : Number(analysis.current_price);
      const marketValue = priceSnapshot == null ? null : priceSnapshot * shares;
      const effectiveCostBasis =
        holding.cost_basis != null
          ? Number(holding.cost_basis)
          : holding.avg_cost_per_share != null
            ? Number(holding.avg_cost_per_share) * shares
            : null;
      const gainLoss =
        marketValue == null || effectiveCostBasis == null
          ? null
          : marketValue - effectiveCostBasis;
      const gainLossPct =
        gainLoss == null || effectiveCostBasis == null || effectiveCostBasis === 0
          ? null
          : (gainLoss / effectiveCostBasis) * 100;

      return {
        holding,
        priceSnapshot,
        marketValue,
        effectiveCostBasis,
        gainLoss,
        gainLossPct,
        allocationPct: null,
      };
    });
    const totalMarketValue = base.reduce(
      (total, item) => total + (item.marketValue ?? 0),
      0
    );

    return base.map((item) => ({
      ...item,
      allocationPct:
        item.marketValue == null || totalMarketValue <= 0
          ? null
          : (item.marketValue / totalMarketValue) * 100,
    }));
  }, [analysisById, holdings]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading portfolio...
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive/30">
        <CardContent className="p-6">
          <h2 className="text-lg font-semibold">Portfolio unavailable</h2>
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
          <Button className="mt-4" variant="outline" onClick={() => void load()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="border-b px-5 py-4">
        <h2 className="font-semibold">Active paper holdings</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Current price and gain/loss use the analysis-time price snapshot, not a live quote.
        </p>
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[1040px] text-left text-sm">
          <thead className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              {[
                "Symbol",
                "Shares",
                "Average cost",
                "Cost basis",
                "Current price",
                "Market value",
                "Gain / loss",
                "Allocation",
                "Status",
              ].map((heading) => (
                <th key={heading} className="px-4 py-3 font-medium">
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {metrics.length === 0 && (
              <tr>
                <td colSpan={9} className="h-52 px-6 text-center">
                  <p className="text-sm font-medium">No active holdings</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Approved analyses can be recorded here as paper holdings.
                  </p>
                </td>
              </tr>
            )}
            {metrics.map((item) => {
              const { holding } = item;
              return (
                <tr key={holding.id} className="align-top hover:bg-muted/30">
                  <td className="px-4 py-4">
                    <p className="font-semibold">{holding.tickers?.symbol ?? "—"}</p>
                    <p className="mt-0.5 max-w-40 truncate text-xs text-muted-foreground">
                      {holding.tickers?.name ?? "Unknown company"}
                    </p>
                  </td>
                  <td className="px-4 py-4 tabular-nums">{formatShares(holding.shares)}</td>
                  <td className="px-4 py-4 tabular-nums">
                    {formatMoney(
                      holding.avg_cost_per_share == null
                        ? null
                        : Number(holding.avg_cost_per_share)
                    )}
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {formatMoney(item.effectiveCostBasis)}
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {formatMoney(item.priceSnapshot)}
                  </td>
                  <td className="px-4 py-4 font-medium tabular-nums">
                    {formatMoney(item.marketValue)}
                  </td>
                  <td className={`px-4 py-4 tabular-nums ${gainLossClass(item.gainLoss)}`}>
                    <p className="font-medium">{formatMoney(item.gainLoss)}</p>
                    <p className="mt-0.5 text-xs">
                      {item.gainLossPct == null
                        ? "—"
                        : `${item.gainLossPct >= 0 ? "Gain" : "Loss"} ${Math.abs(
                            item.gainLossPct
                          ).toFixed(1)}%`}
                    </p>
                  </td>
                  <td className="px-4 py-4 tabular-nums">
                    {item.allocationPct == null ? "—" : `${item.allocationPct.toFixed(1)}%`}
                  </td>
                  <td className="px-4 py-4">
                    <Badge variant="secondary" className="capitalize">
                      {holding.status.replaceAll("_", " ")}
                    </Badge>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="divide-y md:hidden">
        {metrics.length === 0 && (
          <div className="flex h-52 flex-col items-center justify-center px-6 text-center">
            <p className="text-sm font-medium">No active holdings</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Approved analyses can be recorded here as paper holdings.
            </p>
          </div>
        )}
        {metrics.map((item) => {
          const { holding } = item;
          return (
            <article key={holding.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{holding.tickers?.symbol ?? "—"}</h3>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {holding.tickers?.name ?? "Unknown company"}
                  </p>
                </div>
                <Badge variant="secondary" className="capitalize">
                  {holding.status.replaceAll("_", " ")}
                </Badge>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
                {[
                  ["Shares", formatShares(holding.shares)],
                  [
                    "Average cost",
                    formatMoney(
                      holding.avg_cost_per_share == null
                        ? null
                        : Number(holding.avg_cost_per_share)
                    ),
                  ],
                  ["Cost basis", formatMoney(item.effectiveCostBasis)],
                  ["Price snapshot", formatMoney(item.priceSnapshot)],
                  ["Market value", formatMoney(item.marketValue)],
                  [
                    "Allocation",
                    item.allocationPct == null ? "—" : `${item.allocationPct.toFixed(1)}%`,
                  ],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                      {label}
                    </dt>
                    <dd className="mt-1 font-medium tabular-nums">{value}</dd>
                  </div>
                ))}
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Gain / loss
                  </dt>
                  <dd className={`mt-1 font-medium tabular-nums ${gainLossClass(item.gainLoss)}`}>
                    {formatMoney(item.gainLoss)}
                    {item.gainLossPct == null
                      ? ""
                      : ` · ${item.gainLossPct >= 0 ? "Gain" : "Loss"} ${Math.abs(
                          item.gainLossPct
                        ).toFixed(1)}%`}
                  </dd>
                </div>
              </dl>
              <div className="mt-4 border-t pt-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Notes</p>
                <p className="mt-1 text-sm text-muted-foreground">{holding.notes || "—"}</p>
              </div>
            </article>
          );
        })}
      </div>
    </Card>
  );
}
