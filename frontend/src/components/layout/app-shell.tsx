"use client";

import {
  BarChart3,
  BriefcaseBusiness,
  Inbox,
  LayoutDashboard,
  PanelLeft,
  Settings,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { AuthStatus } from "@/components/auth/auth-status";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const navigation = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Analysis Inbox", href: "/inbox", icon: Inbox },
  { label: "Portfolio", href: "/portfolio", icon: BriefcaseBusiness },
  { label: "Screening Runs", href: "/screener", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];

function isActivePath(pathname: string, href: string) {
  return href === "/" ? pathname === href : pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const activeItem =
    navigation.find((item) => isActivePath(pathname, item.href)) ?? navigation[0];

  return (
    <div className="min-h-screen bg-muted/25">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r bg-card lg:flex">
        <div className="flex h-16 items-center gap-3 border-b px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <PanelLeft className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <Link href="/" className="block truncate text-sm font-semibold tracking-tight">
              Research Ledger
            </Link>
            <p className="truncate text-[11px] text-muted-foreground">Analyst Workbench</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3" aria-label="Primary navigation">
          <p className="px-3 pb-2 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Workspace
          </p>
          {navigation.map((item) => {
            const active = isActivePath(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-9 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t p-4">
          <div className="rounded-md border bg-muted/30 p-3">
            <div className="flex items-center gap-2 text-xs font-medium">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Human review required
            </div>
            <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground">
              Portfolio actions create paper holdings only.
            </p>
          </div>
        </div>
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b bg-background/95 px-4 backdrop-blur sm:px-6 lg:h-16 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href="/"
              className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground lg:hidden"
              aria-label="Open dashboard"
            >
              <PanelLeft className="h-4 w-4" />
            </Link>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{activeItem.label}</p>
              <p className="hidden text-xs text-muted-foreground sm:block">
                Investment research workspace
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Badge variant="outline" className="hidden gap-1.5 font-normal text-muted-foreground sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Paper research
            </Badge>
            <AuthStatus />
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
