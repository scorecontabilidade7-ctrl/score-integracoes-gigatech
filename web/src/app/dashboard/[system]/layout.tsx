import { TopNavbar } from "@/components/top-navbar"

export default async function SystemLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ system: string }>
}) {
  const { system } = await params
  
  return (
    <div className="flex-1 flex flex-col">
      <TopNavbar systemId={system} />
      <main className="flex-1 p-6 md:p-8 font-ui max-w-7xl mx-auto w-full">
        {children}
      </main>
    </div>
  )
}
