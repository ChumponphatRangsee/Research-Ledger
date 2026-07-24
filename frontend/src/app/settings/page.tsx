import { SlidersHorizontal } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workspace"
        title="Settings"
        description="Manage research preferences, data sources, and account settings as those controls become available."
      />

      <Card>
        <CardContent className="flex min-h-56 flex-col items-center justify-center p-8 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-md border bg-muted/40">
            <SlidersHorizontal className="h-5 w-5 text-muted-foreground" />
          </div>
          <h2 className="mt-4 text-sm font-semibold">Settings foundation ready</h2>
          <p className="mt-1 max-w-md text-sm leading-6 text-muted-foreground">
            Preference controls will live here. No account or research settings are currently
            exposed by the API.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
