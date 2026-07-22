import { PortfolioList } from "@/components/portfolio/portfolio-list";

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Portfolio</h1>
        <p className="mt-2 text-muted-foreground">
          Holdings created from approved inbox recommendations.
        </p>
      </div>
      <PortfolioList />
    </div>
  );
}
