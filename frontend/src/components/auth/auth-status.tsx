"use client";

import { useEffect, useState } from "react";
import type { User } from "@supabase/supabase-js";
import { Loader2, LogOut, UserCircle2 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { createClient, hasSupabaseBrowserConfig } from "@/lib/supabase/client";

export function AuthStatus() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    let mounted = true;
    if (!hasSupabaseBrowserConfig()) {
      setLoading(false);
      return;
    }

    const supabase = createClient();

    void supabase.auth.getUser().then(({ data }) => {
      if (!mounted) return;
      setUser(data.user ?? null);
      setLoading(false);
    });

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => {
      mounted = false;
      data.subscription.unsubscribe();
    };
  }, []);

  async function handleSignOut() {
    setSigningOut(true);
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
    } finally {
      setSigningOut(false);
    }
    router.replace("/login");
    router.refresh();
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Checking session
      </div>
    );
  }

  if (!user) {
    const redirectTo = pathname === "/login" ? "/" : pathname;
    return (
      <Button variant="outline" size="sm" asChild>
        <Link href={`/login?redirectTo=${encodeURIComponent(redirectTo)}`}>
          <UserCircle2 className="h-4 w-4" />
          Sign in
        </Link>
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <div className="hidden max-w-56 truncate text-right text-xs text-muted-foreground sm:block">
        {user.email}
      </div>
      <Button variant="outline" size="sm" onClick={() => void handleSignOut()} disabled={signingOut}>
        {signingOut ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" />}
        Sign out
      </Button>
    </div>
  );
}
