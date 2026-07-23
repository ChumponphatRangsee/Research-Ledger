"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Loader2, Play } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  fetchLatestScreeningRun,
  fetchScreeningResults,
  runSectorScreener,
  type ScreeningResult,
  type ScreeningRun,
} from "@/lib/api";

const TOP_CANDIDATES = 20;

function errorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return "Please sign in again to use the screener.";
  }
  return error instanceof Error ? error.message : "The screening request failed.";
}

function displayScore(value: number | null) {
  return value == null ? "—" : Number(value).toFixed(1);
}

function statusClass(passed: boolean) {
  return passed
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700"
    : "border-slate-500/30 bg-slate-500/10 text-slate-700";
}

export function ScreenerDashboard() {
  const [run, setRun] = useState<ScreeningRun | null>(null);
  const [results, setResults] = useState<ScreeningResult[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [previousRunId, setPreviousRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const latest = await fetchLatestScreeningRun();
    setRun(latest);
    if (latest?.status === "completed") {
      setResults(await fetchScreeningResults(latest.id));
    }
    return latest;
  }, []);

  useEffect(() => {
    refresh().catch((err) => setError(errorMessage(err)));
  }, [refresh]);

  useEffect(() => {
    if (!starting && run?.status !== "running") return;
    const timer = window.setInterval(() => {
      refresh()
        .then((latest) => {
          const newRunObserved = latest && latest.id !== previousRunId;
          if (newRunObserved && latest.status !== "running") {
            setStarting(false);
          }
        })
        .catch((err) => {
          setStarting(false);
          setError(errorMessage(err));
        });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [previousRunId, refresh, run?.status, starting]);

  const handleRun = async () => {
    try {
      setError(null);
      setPreviousRunId(run?.id ?? null);
      setStarting(true);
      setResults([]);
      await runSectorScreener(TOP_CANDIDATES);
    } catch (err) {
      setStarting(false);
      setError(errorMessage(err));
    }
  };

  const running = starting || run?.status === "running";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Quantitative Screener</h1>
        <p className="mt-2 text-muted-foreground">
          Sector-aware deterministic scoring before AI research begins.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run Screener</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-sm text-muted-foreground">Universe</p>
              <p className="font-medium">Starter Universe</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Top Candidates</p>
              <p className="font-medium">{TOP_CANDIDATES}</p>
            </div>
          </div>
          <Button className="mt-5" disabled={running} onClick={handleRun}>
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {running ? "Screening…" : "Run Screening"}
          </Button>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {run && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Scanned", run.requested_count],
            ["Passed", run.passed_count],
            ["Selected for AI", run.selected_count],
            ["Data errors", run.failed_count],
          ].map(([label, value]) => (
            <Card key={String(label)}>
              <CardContent className="p-5">
                <p className="text-sm text-muted-foreground">{label}</p>
                <p className="mt-1 text-2xl font-semibold">{value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Screening Results</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full text-left text-sm">
              <thead className="border-y bg-muted/50 text-muted-foreground">
                <tr>
                  {["Rank", "Ticker", "Company", "Business Model", "Score", "Confidence", "Quality", "Growth", "Valuation", "Status", ""].map((heading) => (
                    <th key={heading} className="px-4 py-3 font-medium">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.map((result, index) => (
                  <Fragment key={result.id}>
                    <tr
                      className="cursor-pointer border-b hover:bg-muted/40"
                      onClick={() => setExpanded(expanded === result.id ? null : result.id)}
                    >
                      <td className="px-4 py-3">{index + 1}</td>
                      <td className="px-4 py-3 font-semibold">{result.tickers?.symbol ?? "—"}</td>
                      <td className="max-w-44 truncate px-4 py-3">{result.tickers?.name ?? "Unknown"}</td>
                      <td className="px-4 py-3 capitalize">{result.business_model.replaceAll("_", " ")}</td>
                      <td className="px-4 py-3 font-semibold">{displayScore(result.total_score)}</td>
                      <td className="px-4 py-3">{displayScore(result.confidence_score)}</td>
                      <td className="px-4 py-3">{displayScore(result.quality_score)}</td>
                      <td className="px-4 py-3">{displayScore(result.growth_score)}</td>
                      <td className="px-4 py-3">{displayScore(result.valuation_score)}</td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={statusClass(result.passed)}>
                          {result.passed ? "Passed" : "Not selected"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        {expanded === result.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </td>
                    </tr>
                    {expanded === result.id && (
                      <tr className="border-b bg-muted/20">
                        <td colSpan={11} className="px-6 py-5">
                          <div className="grid gap-6 lg:grid-cols-3">
                            <section>
                              <h3 className="font-semibold">Why this stock scored well</h3>
                              <h4 className="mt-3 text-sm font-medium">Strengths</h4>
                              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                                {(result.strengths.length ? result.strengths : ["No strong signal with available data"]).map((item) => <li key={item}>{item}</li>)}
                              </ul>
                              <h4 className="mt-3 text-sm font-medium">Warnings</h4>
                              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                                {[...result.warnings, ...result.failure_reasons].map((item) => <li key={item}>{item}</li>)}
                              </ul>
                            </section>
                            <section>
                              <h3 className="font-semibold">Category breakdown</h3>
                              <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-background p-3 text-xs">
                                {JSON.stringify(result.score_breakdown, null, 2)}
                              </pre>
                            </section>
                            <section>
                              <h3 className="font-semibold">Raw financial metrics</h3>
                              <p className="mt-1 text-xs text-muted-foreground">
                                Model: {result.business_model.replaceAll("_", " ")}
                              </p>
                              <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-background p-3 text-xs">
                                {JSON.stringify(result.metrics, null, 2)}
                              </pre>
                            </section>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
