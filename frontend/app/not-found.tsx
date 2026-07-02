import Link from "next/link";
import { SearchX, Home } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-20 text-center space-y-5">
      <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-slate-100 text-slate-400">
        <SearchX className="h-7 w-7" />
      </span>
      <div className="space-y-1.5">
        <h1 className="text-xl font-bold tracking-tight text-slate-900">Page not found</h1>
        <p className="text-sm text-slate-500">The page you're looking for doesn't exist or has moved.</p>
      </div>
      <Link href="/" className={cn(buttonVariants())}>
        <Home className="h-4 w-4" /> Back to home
      </Link>
    </div>
  );
}
