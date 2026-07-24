import { InboxList } from "@/components/inbox/inbox-list";
import { PageHeader } from "@/components/layout/page-header";

export default function InboxPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Human review"
        title="Analysis Inbox"
        description="Review AI-assisted research, approve or reject the thesis, and create paper holdings only after a human decision."
      />
      <InboxList />
    </div>
  );
}
