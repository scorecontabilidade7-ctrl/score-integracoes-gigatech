import { createClient } from '@/utils/supabase/server'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Users, ShoppingCart, Package, UsersRound } from 'lucide-react'

export default async function DashboardOverview() {
  const supabase = await createClient()

  // Buscar totais das tabelas
  const [{ count: totalClientes }, { count: totalVendas }, { count: totalEstoque }, { count: totalVendedores }] = await Promise.all([
    supabase.from('gigatech_clientes_config').select('*', { count: 'exact', head: true }).eq('ativo', true),
    supabase.from('gigatech_vendas').select('*', { count: 'exact', head: true }),
    supabase.from('gigatech_estoque').select('*', { count: 'exact', head: true }),
    supabase.from('gigatech_vendedores').select('*', { count: 'exact', head: true })
  ])

  // Aqui no futuro implementaremos a lógica de evolução diária no Recharts (buscar agrupado por data)

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-2xl font-bold tracking-tight">Overview</h2>
        <p className="text-muted-foreground text-sm">Acompanhe o volume de processamento do robô da Giga Tech.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Clientes Ativos</CardTitle>
            <Users className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalClientes || 0}</div>
          </CardContent>
        </Card>
        
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Vendas Processadas</CardTitle>
            <ShoppingCart className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalVendas?.toLocaleString('pt-BR') || 0}</div>
          </CardContent>
        </Card>
        
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Registros de Estoque</CardTitle>
            <Package className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalEstoque?.toLocaleString('pt-BR') || 0}</div>
          </CardContent>
        </Card>
        
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Vendedores</CardTitle>
            <UsersRound className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalVendedores?.toLocaleString('pt-BR') || 0}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-1">
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl min-h-[400px]">
          <CardHeader>
            <CardTitle className="text-base font-medium">Evolução de Processamento</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-center text-sm text-muted-foreground min-h-[300px]">
            {/* O Gráfico do Recharts vai entrar aqui futuramente após agregarmos via RPC ou SQL View */}
            A evolução diária será renderizada após a primeira extração bem sucedida.
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
