import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "LinguistOS",
  description: "Vocabulary practice powered by morpho-syntactic generation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-gray-900 antialiased">{children}</body>
    </html>
  );
}
