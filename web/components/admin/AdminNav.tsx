"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"

const TABS = [
  { href: "/admin/schedule", label: "Schedule", icon: "🗓" },
  { href: "/admin/outfits", label: "Outfits", icon: "👗" },
  { href: "/admin/wardrobe", label: "Wardrobe", icon: "🧺" },
  { href: "/admin/metrics", label: "Metrics", icon: "📈" },
]

export default function AdminNav({ actions }: { actions?: React.ReactNode }) {
  const pathname = usePathname()
  const isActive = (href: string) => pathname.startsWith(href)
  const [overflow, setOverflow] = useState(false)

  return (
    <>
      {/* Mobile: top bar with overflow for global actions */}
      <div className="fixed inset-x-0 top-0 z-40 flex items-center justify-between border-b border-line/70 bg-background/95 px-4 py-2.5 backdrop-blur md:hidden">
        <img src="/logo_cropped.png" alt="Vance Archives" className="h-7 w-auto" />
        <button
          onClick={() => setOverflow((v) => !v)}
          className="px-2 text-xl leading-none text-muted"
          aria-label="actions"
        >
          ⋯
        </button>
      </div>
      {overflow && (
        <div
          className="fixed inset-0 z-40 bg-stone-900/30 md:hidden"
          onClick={() => setOverflow(false)}
        >
          <div
            className="absolute right-3 top-12 w-60 rounded-sm border border-line bg-background p-3 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            {actions}
          </div>
        </div>
      )}

      {/* Desktop: left sidebar */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-line/70 bg-surface/60 p-5 md:flex">
        <img src="/logo_cropped.png" alt="Vance Archives" className="mb-8 h-8 w-auto" />
        <nav className="flex flex-col gap-1">
          {TABS.map((t) => (
            <Link
              key={t.href}
              href={t.href}
              className={`rounded-sm px-3 py-2 text-sm transition-colors ${
                isActive(t.href)
                  ? "bg-accent/10 text-accent"
                  : "text-muted hover:text-foreground"
              }`}
            >
              {t.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-2 pt-6">{actions}</div>
      </aside>

      {/* Mobile: bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line/70 bg-background/95 backdrop-blur md:hidden">
        {TABS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[0.6rem] tracking-wider uppercase ${
              isActive(t.href) ? "text-accent" : "text-muted"
            }`}
          >
            <span className="text-base">{t.icon}</span>
            {t.label}
          </Link>
        ))}
      </nav>
    </>
  )
}
