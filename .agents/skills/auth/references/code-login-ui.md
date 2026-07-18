# Login UI: Pages and Components

Battle-tested in production. All shadcn-based (Button, Input, Label, Card, Avatar, DropdownMenu must exist in the target repo). Same find/replace list as code-auth-core.md. Route group: pages live under `app/(auth)/` so `/login`, `/verify`, `/popup-complete`, `/register` share one centered-card layout.

## 1. Auth layout (`app/(auth)/layout.tsx`)

```tsx
import type { PropsWithChildren } from "react";
import Link from "next/link";
import { Send } from "lucide-react";

import { Card } from "@/components/ui/card";

export default function AuthLayout({ children }: PropsWithChildren) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      <Link
        href="/"
        className="mb-8 flex items-center gap-2 transition-opacity hover:opacity-80"
      >
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Send className="size-4" />
        </span>
        <span className="font-display text-lg font-semibold">Acme</span>
      </Link>

      <Card className="w-full max-w-sm p-8">{children}</Card>
    </div>
  );
}
```

## 2. Login page (`app/(auth)/login/page.tsx`)

```tsx
import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import type { Metadata } from "next";

import { LoginForm } from "@/components/auth/login-form";
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to Acme to access your dashboard.",
};

export default function LoginPage() {
  return (
    <>
      <div className="mb-6 space-y-1.5">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Sign in
        </h1>
        <p className="text-sm text-muted-foreground">
          We&apos;ll email you a magic link. No password needed.
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex justify-center py-8">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <div className="flex flex-col gap-4">
          <LoginForm />

          <div className="flex items-center gap-3 text-xs text-muted-foreground before:flex-1 before:border-t before:border-border after:flex-1 after:border-t after:border-border">
            or
          </div>

          <GoogleSignInButton />
        </div>
      </Suspense>

      <p className="mt-6 text-center text-xs text-muted-foreground/75">
        First time here? Your account is created automatically on sign-in.
      </p>
    </>
  );
}
```

## 3. Magic-link form (`components/auth/login-form.tsx`)

Plain useState + zod, deliberately no react-hook-form dependency for one field.

```tsx
"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { InboxIcon, Loader2 } from "lucide-react";
import { z } from "zod";

import { signIn } from "@acme/auth/client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const emailSchema = z.string().email("Please enter a valid email address");

/**
 * Magic-link sign-in: email field only. On success the user is sent to
 * /verify which tells them to check their inbox.
 */
export function LoginForm() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const parsed = emailSchema.safeParse(email.trim());
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Invalid email");
      return;
    }

    startTransition(async () => {
      await signIn.magicLink({
        email: parsed.data,
        callbackURL: "/dashboard",
        fetchOptions: {
          onSuccess: () => {
            router.push(`/verify?email=${encodeURIComponent(parsed.data)}`);
          },
          onError: ({ error: authError }) => {
            setError(
              authError.message ?? "Failed to send the magic link. Try again.",
            );
          },
        },
      });
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="h-10"
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button type="submit" disabled={pending} className="mt-1 h-10 w-full">
        {pending ? (
          <Loader2 className="animate-spin" />
        ) : (
          <InboxIcon className="size-4" />
        )}
        Send me a magic link
      </Button>
    </form>
  );
}
```

## 4. Popup Google button (`components/auth/google-sign-in-button.tsx`)

The popup keeps users on YOUR site instead of a full-page redirect to Google. Requirements: the app must NOT send Cross-Origin-Opener-Policy headers (COOP severs `window.opener` and the popup can't message back); CSP `form-action`/`connect-src` must allow `accounts.google.com`.

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { signIn } from "@acme/auth/client";

import { Button } from "@/components/ui/button";

const POPUP_NAME = "acme-google-signin";
export const OAUTH_COMPLETE_MESSAGE = "acme:oauth-complete";

/**
 * Open a centered OAuth popup. Must be called synchronously inside the click
 * handler so popup blockers treat it as user-initiated; the OAuth URL is
 * assigned to it afterwards once BetterAuth returns it.
 */
function openCenteredPopup(): Window | null {
  const width = 480;
  const height = 640;
  const left = window.screenX + Math.max(0, (window.outerWidth - width) / 2);
  const top = window.screenY + Math.max(0, (window.outerHeight - height) / 2);
  return window.open(
    "about:blank",
    POPUP_NAME,
    `width=${width},height=${height},left=${left},top=${top},popup=1`,
  );
}

/**
 * Google sign-in that keeps the user on the site: the consent screen opens in
 * a small popup (callback lands on /popup-complete, which posts a message back
 * and closes itself). Falls back to a classic full-page redirect when the
 * popup is blocked.
 */
export function GoogleSignInButton() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => () => cleanupRef.current?.(), []);

  async function handleClick() {
    setPending(true);
    const popup = openCenteredPopup();

    const { data, error } = await signIn.social({
      provider: "google",
      callbackURL: "/popup-complete",
      disableRedirect: true,
    });

    if (error || !data?.url) {
      popup?.close();
      setPending(false);
      return;
    }

    if (!popup || popup.closed) {
      // Popup blocked: fall back to redirecting this tab. /popup-complete
      // detects the missing opener and forwards to /dashboard.
      window.location.href = data.url;
      return;
    }

    popup.location.href = data.url;

    let done = false;
    const finish = () => {
      done = true;
      cleanup();
      router.push("/dashboard");
      router.refresh();
    };

    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      if (
        (event.data as { type?: string } | null)?.type ===
        OAUTH_COMPLETE_MESSAGE
      ) {
        finish();
      }
    };
    window.addEventListener("message", onMessage);

    // If the user closes the popup without completing, re-enable the button.
    // The small grace period lets a just-sent completion message win the race.
    const closedPoll = window.setInterval(() => {
      if (!popup.closed) return;
      window.clearInterval(closedPoll);
      window.setTimeout(() => {
        if (!done) {
          cleanup();
          setPending(false);
        }
      }, 400);
    }, 500);

    const cleanup = () => {
      window.removeEventListener("message", onMessage);
      window.clearInterval(closedPoll);
      cleanupRef.current = null;
    };
    cleanupRef.current = cleanup;
  }

  return (
    <Button
      type="button"
      variant="outline"
      onClick={handleClick}
      disabled={pending}
      className="h-10 w-full gap-2"
    >
      {pending ? <Loader2 className="animate-spin" /> : <GoogleIcon />}
      Continue with Google
    </Button>
  );
}

/* Google brand mark (official multi-color G). */
function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}
```

## 5. Popup bridge page (`app/(auth)/popup-complete/page.tsx` + `components/auth/popup-complete.tsx`)

```tsx
// app/(auth)/popup-complete/page.tsx
import type { Metadata } from "next";

import { PopupComplete } from "@/components/auth/popup-complete";

export const metadata: Metadata = {
  title: "Signing you in",
  robots: { index: false },
};

/**
 * OAuth popup landing target. The Google flow inside the popup ends here;
 * the client component notifies the opener tab and closes the window.
 */
export default function PopupCompletePage() {
  return <PopupComplete />;
}
```

```tsx
// components/auth/popup-complete.tsx
"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";

import { OAUTH_COMPLETE_MESSAGE } from "@/components/auth/google-sign-in-button";

/**
 * Runs inside the OAuth popup once Google redirects back. Tells the opener
 * tab the sign-in finished, then closes itself. When there is no opener
 * (popup was blocked and the flow ran as a full-page redirect), forward to
 * the dashboard directly.
 */
export function PopupComplete() {
  useEffect(() => {
    if (window.opener && window.opener !== window) {
      (window.opener as Window).postMessage(
        { type: OAUTH_COMPLETE_MESSAGE },
        window.location.origin,
      );
      window.close();
    } else {
      window.location.replace("/dashboard");
    }
  }, []);

  return (
    <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" />
      Signing you in...
    </div>
  );
}
```

## 6. Verify page (`app/(auth)/verify/page.tsx`)

```tsx
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Check your inbox",
  description: "Check your inbox to sign in.",
  robots: { index: false },
};

type PageProps = {
  searchParams: Promise<{ email?: string }>;
};

export default async function VerifyPage({ searchParams }: PageProps) {
  const { email } = await searchParams;

  return (
    <>
      <div className="mb-6 space-y-1.5">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Check your inbox
        </h1>
        <p className="text-sm text-muted-foreground">
          We sent a magic link to{" "}
          <strong className="text-foreground">{email ?? "your email"}</strong>.
          Click it to sign in.
        </p>
      </div>

      <p className="text-xs text-muted-foreground/75">
        No email? Check your spam folder or{" "}
        <Link
          href="/login"
          className="font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          try a different address
        </Link>
        .
      </p>
    </>
  );
}
```

## 7. Register redirect (`app/(auth)/register/page.tsx`)

Registration collapses into /login (accounts auto-create). Keep the route as a redirect so old links and marketing CTAs don't 404; point all "Sign up" CTAs at `/login`.

```tsx
import { redirect } from "next/navigation";

export default function RegisterPage() {
  redirect("/login");
}
```

## 8. Header user menu (`components/auth/user-menu.tsx`)

Sign-in button when logged out, Google avatar with dropdown (name/email + Dashboard + Log out) when logged in. The `signIn*` props let the logged-out button match whatever header hosts it.

```tsx
"use client";

import type { ComponentProps } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LayoutDashboard, LogOut } from "lucide-react";
import { motion } from "motion/react";

import { signOut, useSession } from "@acme/auth/client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function getInitials(name: string | null | undefined): string {
  if (!name) return "?";
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

type UserMenuProps = {
  /** Styling for the logged-out button so it can match its host header. */
  signInVariant?: ComponentProps<typeof Button>["variant"];
  signInClassName?: string;
  signInLabel?: string;
};

export function UserMenu({
  signInVariant = "ghost",
  signInClassName,
  signInLabel = "Sign in",
}: UserMenuProps) {
  const router = useRouter();
  const { data: session, isPending } = useSession();

  const handleSignOut = async () => {
    await signOut({
      fetchOptions: {
        onSuccess: () => {
          router.refresh();
        },
      },
    });
  };

  // While the session resolves, hold the avatar's footprint so the header
  // doesn't jump, and don't flash "Sign in" at logged-in users.
  if (isPending) {
    return <div aria-hidden="true" className="size-9" />;
  }

  if (!session?.user) {
    return (
      <Button asChild variant={signInVariant} className={signInClassName}>
        <Link href="/login">{signInLabel}</Link>
      </Button>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="flex items-center justify-center"
    >
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          {/* size-9 rounded-md mirrors adjacent icon buttons (e.g. a theme
              toggle) so the header controls align as one row. Use
              rounded-full everywhere instead if your header has no square
              icon buttons. */}
          <button
            type="button"
            className="flex size-9 items-center justify-center overflow-hidden rounded-md outline-none ring-offset-background transition-all duration-100 hover:ring-2 hover:ring-ring hover:ring-offset-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <Avatar className="size-9 cursor-pointer rounded-md">
              <AvatarImage
                src={session.user.image ?? undefined}
                alt={
                  session.user.name
                    ? `${session.user.name}'s profile picture`
                    : "Profile picture"
                }
              />
              <AvatarFallback className="rounded-md">
                {getInitials(session.user.name)}
              </AvatarFallback>
            </Avatar>
          </button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          side="bottom"
          align="end"
          className="w-56 rounded-lg"
        >
          <DropdownMenuLabel className="max-w-48 truncate font-normal leading-relaxed">
            {session.user.name || "User"}
            {session.user.name !== session.user.email && (
              <div className="truncate text-xs text-muted-foreground">
                {session.user.email}
              </div>
            )}
          </DropdownMenuLabel>

          <DropdownMenuSeparator />

          <DropdownMenuItem asChild className="cursor-pointer">
            <Link href="/dashboard" className="flex items-center gap-2">
              <LayoutDashboard className="size-4 opacity-75" />
              Dashboard
            </Link>
          </DropdownMenuItem>

          <DropdownMenuItem
            onClick={handleSignOut}
            className="flex cursor-pointer items-center gap-2"
          >
            <LogOut className="size-4 opacity-75" />
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </motion.div>
  );
}
```

### Header wiring

Render `<UserMenu />` in the SITE'S REAL header (verify which header component the landing layout actually imports; a wrong, dead header component is an easy round to waste here). Hide the signup CTA when logged in:

```tsx
const { data: session, isPending } = useSession();
const showCta = !isPending && !session?.user;
// ...
{
  showCta && (
    <Button asChild>
      <Link href="/login">Get started</Link>
    </Button>
  );
}
<UserMenu
  signInVariant="outline"
  signInClassName="max-sm:hidden"
  signInLabel="Log in"
/>;
```
