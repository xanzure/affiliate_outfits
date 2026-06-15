import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {children}
        <footer className="mt-auto px-6 py-10 sm:px-12 lg:px-20 flex gap-8 items-center justify-center border-t border-stone-200">
          <Link href="/terms" className="text-xs tracking-widest text-stone-300 uppercase hover:text-stone-500 transition-colors">
            Terms
          </Link>
          <Link href="/privacy" className="text-xs tracking-widest text-stone-300 uppercase hover:text-stone-500 transition-colors">
            Privacy
          </Link>
          <span className="text-xs tracking-widest text-stone-200 uppercase">
            © {new Date().getFullYear()} Vance Archives
          </span>
        </footer>
      </body>
    </html>
  );
}
