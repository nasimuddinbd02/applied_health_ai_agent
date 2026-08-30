"use client";
import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

/** Lightweight checkbox built on a native input (no extra runtime dep). API is
 * a controlled `checked` + `onCheckedChange`, matching how shadcn's radix
 * checkbox is consumed so call sites read the same. */
export interface CheckboxProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  id?: string;
}

const Checkbox = React.forwardRef<HTMLButtonElement, CheckboxProps>(
  ({ checked = false, onCheckedChange, disabled, className, id }, ref) => (
    <button
      ref={ref}
      id={id}
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange?.(!checked)}
      className={cn(
        "peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 flex items-center justify-center transition-colors",
        checked ? "bg-primary text-primary-foreground" : "bg-background",
        className,
      )}
    >
      {checked && <Check className="h-3.5 w-3.5" />}
    </button>
  ),
);
Checkbox.displayName = "Checkbox";

export { Checkbox };
