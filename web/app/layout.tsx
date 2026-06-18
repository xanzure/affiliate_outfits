import type { Metadata } from "next";
import { Geist, Geist_Mono, Cormorant_Garamond } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const cormorant = Cormorant_Garamond({
  variable: "--font-cormorant",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "Vance Archives",
  description: "A curated archive of outfit concepts and looks.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${cormorant.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
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
      </body>
    </html>
  );
}
