import { PageHeader } from "@/components/layout/page-header";
import { PortfolioList } from "@/components/portfolio/portfolio-list";

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Paper portfolio"
        title="Portfolio"
        description="Monitor active paper holdings created from reviewed and approved investment analyses."
      />
      <PortfolioList />
    </div>
  );
}
