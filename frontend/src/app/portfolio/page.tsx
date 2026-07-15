import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Portfolio</h1>
        <p className="mt-2 text-muted-foreground">
          Holdings created from approved inbox recommendations.
        </p>
      </div>
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
    </div>
  );
}
