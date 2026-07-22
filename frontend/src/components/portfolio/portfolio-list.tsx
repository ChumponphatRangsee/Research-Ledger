"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, fetchPortfolio, type PortfolioHolding } from "@/lib/api";

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return "Please sign in again to view your portfolio.";
  }
  if (error instanceof Error) return error.message;
  return "Could not load portfolio.";
}

export function PortfolioList() {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      const data = await fetchPortfolio();
      setHoldings(data);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

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
      <Card>
        <CardContent className="p-6">
          <h2 className="text-lg font-semibold">Error</h2>
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
          <Button className="mt-4" onClick={load}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  if (holdings.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No holdings yet</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Approve items in the inbox and execute trades to build your portfolio.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      {holdings.map((holding) => (
        <Card key={holding.id}>
          <CardContent className="flex flex-col gap-3 p-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold">{holding.tickers?.symbol ?? "Unknown"}</h3>
              <p className="text-sm text-muted-foreground">
                {holding.tickers?.name ?? "Unlabeled holding"}
              </p>
            </div>
            <div className="text-left sm:text-right">
              <p className="text-xl font-semibold">{holding.shares}</p>
              <p className="text-sm text-muted-foreground">shares</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
