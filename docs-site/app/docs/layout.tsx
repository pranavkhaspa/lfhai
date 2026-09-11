import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { Footer } from "@/components/Footer";

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 lg:ml-[280px]">
          <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8 py-12">
            {children}
          </div>
          <Footer />
        </main>
      </div>
    </div>
  );
}
