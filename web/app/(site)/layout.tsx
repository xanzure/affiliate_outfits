import Link from "next/link";

export default function SiteLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-40 border-b border-line/70 bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between px-5 py-3 sm:px-12 sm:py-4 lg:px-20">
          <Link href="/" className="group flex items-center">
            <img
              src="/logo_cropped.png"
              alt="Vance Archives"
              className="h-9 w-auto object-contain transition-transform duration-300 group-hover:scale-[1.04] sm:h-11"
            />
          </Link>
          <nav className="flex items-center gap-8">
            <Link
              href="/"
              className="text-[0.65rem] tracking-[0.28em] uppercase text-muted transition-colors hover:text-accent sm:text-[0.7rem]"
            >
              Archive
            </Link>
          </nav>
        </div>
      </header>

      <div className="flex-1">{children}</div>

      <footer className="mt-auto border-t border-line/70 px-6 py-12 sm:px-12 lg:px-20">
        <div className="mx-auto flex max-w-[1400px] flex-col items-center gap-4 sm:flex-row sm:justify-between">
          <span className="font-serif text-xl tracking-wide text-foreground/80">
            Vance Archives
          </span>
          <div className="flex items-center gap-8">
            <Link
              href="/terms"
              className="text-[0.7rem] tracking-[0.28em] uppercase text-muted transition-colors hover:text-accent"
            >
              Terms
            </Link>
            <Link
              href="/privacy"
              className="text-[0.7rem] tracking-[0.28em] uppercase text-muted transition-colors hover:text-accent"
            >
              Privacy
            </Link>
            <span className="text-[0.7rem] tracking-[0.28em] uppercase text-muted/60">
              © {new Date().getFullYear()}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
