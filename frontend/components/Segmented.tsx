'use client';

import type { ReactNode } from 'react';

export type SegmentOption<V extends string> = { value: V; label: ReactNode; aria?: string };

/** A segmented choice: role="radiogroup", each option a real button with aria-checked, 44 px high. */
export function Segmented<V extends string>({ label, value, options, onChange, size = 'md' }: {
  label: string; value: V; options: SegmentOption<V>[]; onChange: (v: V) => void; size?: 'md' | 'sm';
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex min-w-0 gap-[2px] rounded-md bg-surface-2 p-[2px]">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          aria-label={o.aria}
          onClick={() => onChange(o.value)}
          className={`flex min-w-0 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-sm px-3 font-semibold ${size === 'sm' ? 'h-11 text-[13px]' : 'h-11 text-[14px]'} ${value === o.value ? 'bg-fg text-bg' : 'bg-transparent text-fg-2 hover:text-fg'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
