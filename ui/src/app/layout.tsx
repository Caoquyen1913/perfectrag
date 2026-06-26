import "./globals.css";
import Providers from "./providers";

export const metadata = {
  title: "perfectRAG",
  description: "Dynamic RAG framework scaffolder",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-50 text-neutral-900">
        <Providers>
          <nav className="border-b bg-white px-6 py-3 flex gap-6">
            <a href="/" className="font-bold">perfectRAG</a>
            <a href="/wizard" className="hover:underline">Wizard</a>
            <a href="/dashboard" className="hover:underline">Dashboard</a>
          </nav>
          <main className="p-6 max-w-6xl mx-auto">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
