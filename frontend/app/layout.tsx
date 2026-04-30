import type { Metadata } from "next";
import { LayoutShell } from "@/components/LayoutShell";
import { QuickCapture } from "@/components/QuickCapture";
import { WordQuickViewModal } from "@/components/WordQuickViewModal";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "LinguistOS — Learn Spanish",
  description:
    "Vocabulary practice powered by morpho-syntactic sentence generation",
  icons: {
    icon: "/icon.png",
    apple: "/apple-icon.png",
  },
  openGraph: {
    title: "LinguistOS — Learn Spanish",
    description: "Vocabulary practice powered by morpho-syntactic sentence generation",
    images: [{ url: "/opengraph-image.png" }],
  },
  twitter: {
    card: "summary",
    images: ["/twitter-image.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <LayoutShell>{children}</LayoutShell>
        <QuickCapture />
        <WordQuickViewModal />
      </body>
    </html>
  );
}
