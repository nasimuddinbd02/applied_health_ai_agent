import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AuthProvider } from "./_auth/AuthContext";
import NavBar from "./_auth/NavBar";
import FloatingChatWidget from "./_components/FloatingChatWidget";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "City Hospital",
  description: "Patient appointments, doctors and treatment records",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans antialiased">
        <AuthProvider>
          <NavBar />
          <main className="mx-auto max-w-6xl px-4 sm:px-6 py-8">{children}</main>
          <FloatingChatWidget />
        </AuthProvider>
      </body>
    </html>
  );
}
