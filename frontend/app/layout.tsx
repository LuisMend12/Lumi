import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import "./globals.css";

// Storm Center type: Barlow for reading, Barlow Condensed for names, chyrons and numbers (#68).
const barlow = Barlow({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const barlowCondensed = Barlow_Condensed({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
});

export const metadata: Metadata = {
  title: "Lumi",
  description: "Winter walking routes for Boston that account for snow, ice, and blocked sidewalks.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${barlow.variable} ${barlowCondensed.variable} antialiased`}
      >
        {/* Clerk Core 3 (v7) wants the provider inside <body>, not wrapping <html>. */}
        <ClerkProvider>{children}</ClerkProvider>
      </body>
    </html>
  );
}
