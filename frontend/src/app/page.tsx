import { TrendingUp, Inbox, Briefcase, Bot } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const stats = [
  { title: "Pending Review", metric: "—", icon: Inbox, href: "/inbox" },
  { title: "Active Holdings", metric: "—", icon: Briefcase, href: "/portfolio" },
  { title: "Today's Screened", metric: "—", icon: TrendingUp, href: "/inbox" },
  { title: "AI Pipelines", metric: "4 agents", icon: Bot, href: "/inbox" },
];

const pipelineStages = ["Researcher", "Financial Analyst", "Valuator", "Decision Maker"];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Research Dashboard</h1>
        <p className="mt-2 text-muted-foreground">
          Automated quantitative screening with AI-driven qualitative research.
          Review recommendations in your inbox before executing trades.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.title} className="p-0">
            <Link href={stat.href} className="block rounded-lg transition-colors hover:bg-accent/50">
              <CardContent className="flex items-center justify-between p-6">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.title}</p>
                  <p className="mt-1 text-2xl font-semibold">{stat.metric}</p>
                </div>
                <stat.icon className="h-8 w-8 text-primary opacity-60" />
              </CardContent>
            </Link>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Pipeline Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Daily Celery screener → LangGraph agents (Researcher → Financial → Valuator → Decision) → Human approval breakpoint → Portfolio execution.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            {pipelineStages.map((stage) => (
              <Badge key={stage} variant="secondary">
                {stage}
              </Badge>
            ))}
          </div>
          <div className="mt-6">
            <Button asChild>
              <Link href="/inbox">Open Analysis Inbox</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
