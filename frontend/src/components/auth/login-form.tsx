"use client";

import { FormEvent, useState } from "react";
import { Loader2, LogIn, Mail } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";

function redirectTarget() {
  if (typeof window === "undefined") return "/";
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("redirectTo");
  if (!requested || !requested.startsWith("/") || requested.startsWith("//")) {
    return "/";
  }
  return requested;
}

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setNotice(null);

    let signInError: Error | null = null;
    try {
      const supabase = createClient();
      const result = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      signInError = result.error;
    } catch (err) {
      signInError = err instanceof Error ? err : new Error("Unable to sign in.");
    }

    setLoading(false);

    if (signInError) {
      setError(signInError.message);
      return;
    }

    router.replace(redirectTarget());
    router.refresh();
  }

  async function handlePasswordReset() {
    const trimmedEmail = email.trim();
    setError(null);
    setNotice(null);

    if (!trimmedEmail) {
      setError("Enter your email first, then request a password reset.");
      return;
    }

    setResetLoading(true);
    try {
      const supabase = createClient();
      const redirectTo =
        typeof window === "undefined"
          ? undefined
          : `${window.location.origin}/auth/update-password`;
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(trimmedEmail, {
        redirectTo,
      });
      if (resetError) throw resetError;
      setNotice("Password reset email sent. Open the link in that email to set a new password.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send password reset email.");
    } finally {
      setResetLoading(false);
    }
  }

  return (
    <Card className="mx-auto w-full max-w-md">
      <CardHeader>
        <CardTitle>Sign in</CardTitle>
        <CardDescription>
          Use the Supabase Auth user created for this Research Ledger project.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>

          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          {notice && (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
              {notice}
            </div>
          )}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
            Sign in
          </Button>

          <Button
            type="button"
            variant="link"
            className="h-auto w-full p-0"
            disabled={resetLoading}
            onClick={() => void handlePasswordReset()}
          >
            {resetLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
            Forgot password?
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
