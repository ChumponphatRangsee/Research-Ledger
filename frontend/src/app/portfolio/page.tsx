import { PageHeader } from "@/components/layout/page-header";
import { PortfolioWorkbench } from "@/components/portfolio/portfolio-workbench";

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investment OS"
        title="Portfolio"
        description="Review what you own, your cost basis, portfolio activity, and any transactions that need human attention."
      />
      <PortfolioWorkbench />
    </div>
  );
}
