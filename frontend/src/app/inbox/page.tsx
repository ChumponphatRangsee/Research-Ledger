import { InboxList } from "@/components/inbox/inbox-list";

export default function InboxPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Analysis Inbox</h1>
        <p className="mt-2 text-muted-foreground">
          AI-analyzed stocks awaiting your decision. Approve to stage for portfolio execution, or discard.
        </p>
      </div>
      <InboxList />
    </div>
  );
}
