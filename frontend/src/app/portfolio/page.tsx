import { PageHeader } from "@/components/layout/page-header";
import { PortfolioWorkbench } from "@/components/portfolio/portfolio-workbench";

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Portfolio ledger"
        title="Portfolio"
        description="Review transaction drafts, inspect confirmed ledger positions, and keep legacy paper holdings visible during migration."
      />
      <PortfolioWorkbench />
    </div>
  );
}
