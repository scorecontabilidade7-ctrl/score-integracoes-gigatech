import type { Metadata } from "next";
import { Inter, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const fontInter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const fontDMSans = DM_Sans({ subsets: ["latin"], variable: "--font-dm-sans" });
const fontJetBrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains-mono" });

export const metadata: Metadata = {
  title: "Score | Giga Tech Automations",
  description: "Orquestrador Multi-tenant da Score Contabilidade",
  icons: {
    icon: "https://lunsyufvxkiivnrhpxpj.supabase.co/storage/v1/object/public/utils/favicon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={`${fontInter.variable} ${fontDMSans.variable} ${fontJetBrains.variable}`}>
      <body className="antialiased font-sans text-base sm:text-lg min-h-full flex flex-col">
        {children}
      </body>
    </html>
  );
}
