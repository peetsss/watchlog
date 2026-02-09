import type { Metadata } from "next";
import { Bebas_Neue, Crimson_Text } from "next/font/google";
import AtmosphericBackground from "@/components/layout/AtmosphericBackground";
import "./globals.css";

const bebasNeue = Bebas_Neue({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-bebas-neue",
});

const crimsonText = Crimson_Text({
  weight: ["400", "600"],
  style: ["normal", "italic"],
  subsets: ["latin"],
  variable: "--font-crimson-text",
});

export const metadata: Metadata = {
  title: "CineCircle",
  description: "Your cinematic social network",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${bebasNeue.variable} ${crimsonText.variable} min-h-screen antialiased`}
        style={{
          background:
            "linear-gradient(to bottom, #0a0a0a 0%, #1a1a2e 50%, #0a0a0a 100%)",
        }}
      >
        <AtmosphericBackground />
        {children}
      </body>
    </html>
  );
}
