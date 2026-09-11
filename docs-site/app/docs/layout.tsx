import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { Footer } from "@/components/Footer";

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <Header />
      <div className="flex">
        <Sidebar />
        <main className="min-w-0 flex-1 lg:pl-64">
          <div className="mx-auto max-w-3xl px-4 pb-8 pt-12 sm:px-6 lg:px-10">
            <article className="doc-content">{children}</article>
          </div>
          <Footer />
        </main>
      </div>
    </div>
  );
}