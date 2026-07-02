"use client";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Route-level error boundary (Next.js convention). Catches render/data
 * errors in the segment — e.g. the backend being down — and offers a retry
 * instead of a white screen. */
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-md py-20 text-center space-y-5">
      <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-amber-100 text-amber-600">
        <AlertTriangle className="h-7 w-7" />
      </span>
      <div className="space-y-1.5">
        <h1 className="text-xl font-bold tracking-tight text-slate-900">Something went wrong</h1>
        <p className="text-sm text-slate-500">
          {error.message || "We couldn't load this page. The server may be briefly unavailable."}
        </p>
      </div>
      <div className="flex items-center justify-center gap-2">
        <Button onClick={reset}>
          <RotateCcw className="h-4 w-4" /> Try again
        </Button>
        <Link href="/" className={cn(buttonVariants({ variant: "outline" }))}>
          <Home className="h-4 w-4" /> Go home
        </Link>
      </div>
    </div>
  );
}
