import Link from 'next/link'
import { Database, Activity, LayoutDashboard, LogOut } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { createClient } from '@/utils/supabase/server'
import { SYSTEMS } from '@/utils/systems'

export const dynamic = 'force-dynamic'

export default async function DashboardSelector() {
  const supabase = await createClient()

  // Buscar contagem de clientes ativos para cada sistema para exibir nos cartões
  const counts = await Promise.all(
    Object.values(SYSTEMS).map(async (sys) => {
      const { count } = await supabase
        .from(sys.configTable)
        .select('*', { count: 'exact', head: true })
        .eq('ativo', true)
      return { id: sys.id, count: count || 0 }
    })
  )

  const countMap = new Map(counts.map((c) => [c.id, c.count]))

  const icons = {
    database: Database,
    activity: Activity,
  }

  return (
    <div className="min-h-screen bg-[#F9FAFB] flex flex-col font-ui">
      {/* Top bar simplificada no portal */}
      <header className="w-full h-20 flex items-center justify-between px-6 md:px-12 border-b border-slate-100 bg-white">
        <img 
          src="https://lunsyufvxkiivnrhpxpj.supabase.co/storage/v1/object/public/utils/logo_completa.png" 
          alt="Score Logo" 
          className="h-11 object-contain"
        />
        <form action="/api/auth/signout" method="POST">
          <Button 
            variant="outline" 
            className="h-10 rounded-full border-red-200 text-red-500 hover:bg-red-50 hover:text-red-600 gap-2 px-4 text-xs font-bold tracking-wider"
          >
            <LogOut className="h-4 w-4" />
            SAIR
          </Button>
        </form>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center p-6 md:p-12 max-w-5xl mx-auto w-full">
        <div className="text-center space-y-3 mb-12">
          <div className="inline-flex p-3 rounded-2xl bg-slate-100 text-slate-800 mb-2">
            <LayoutDashboard className="h-6 w-6" />
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-slate-900 font-heading">
            Portal de Integrações
          </h1>
          <p className="text-slate-500 max-w-md mx-auto text-sm md:text-base">
            Selecione qual sistema de automação e sincronização você deseja monitorar e configurar neste momento.
          </p>
        </div>

        {/* Grid de Cartões */}
        <div className="grid gap-6 md:grid-cols-2 w-full">
          {Object.values(SYSTEMS).map((sys) => {
            const IconComponent = icons[sys.iconName] || Database
            const activeClients = countMap.get(sys.id) || 0

            return (
              <Link key={sys.id} href={`/dashboard/${sys.id}`} className="group block h-full">
                <Card className="border-0 shadow-sm shadow-black/5 hover:shadow-md hover:shadow-black/[0.08] hover:-translate-y-1 transition-all duration-300 rounded-3xl bg-white p-4 h-full border border-transparent hover:border-slate-100 flex flex-col justify-between">
                  <div>
                    <CardHeader className="flex flex-row items-center justify-between pb-4 space-y-0">
                      <div className="inline-flex p-4 rounded-2xl bg-slate-50 text-slate-600 group-hover:bg-slate-900 group-hover:text-white transition-colors duration-300">
                        <IconComponent className="h-6 w-6" />
                      </div>
                      <span className="text-xs font-bold font-data text-emerald-600 bg-emerald-50 border border-emerald-100 px-3 py-1 rounded-full">
                        {activeClients} {activeClients === 1 ? 'cliente ativo' : 'clientes ativos'}
                      </span>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <CardTitle className="text-xl font-bold font-heading text-slate-900 group-hover:text-primary transition-colors">
                        {sys.name}
                      </CardTitle>
                      <CardDescription className="text-slate-500 text-sm leading-relaxed">
                        {sys.description}
                      </CardDescription>
                    </CardContent>
                  </div>
                  <div className="px-6 pb-4 pt-6">
                    <Button className="w-full rounded-2xl font-bold text-xs tracking-wider uppercase bg-slate-100 text-slate-800 group-hover:bg-slate-900 group-hover:text-white transition-all shadow-none">
                      Acessar Painel
                    </Button>
                  </div>
                </Card>
              </Link>
            )
          })}
        </div>
      </main>
    </div>
  )
}
