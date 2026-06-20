import { TopNavbar } from "@/components/top-navbar"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-[#F9FAFB] flex flex-col">
      <TopNavbar />
      <main className="flex-1 p-6 md:p-8 font-ui max-w-7xl mx-auto w-full">
        {children}
      </main>
    </div>
  )
}
