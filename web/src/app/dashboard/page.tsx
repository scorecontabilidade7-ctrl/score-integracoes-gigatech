import { createClient } from '@/utils/supabase/server'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Users, ShoppingCart, Package, UsersRound, AlertCircle } from 'lucide-react'
import { getKestraExecutions } from '@/utils/kestra'
import ProcessChart from '@/components/process-chart'
import RefreshButton from '@/components/refresh-button'

export const dynamic = 'force-dynamic' // Garante que a página sempre busque dados novos

export default async function DashboardOverview() {
  const supabase = await createClient()

  // Buscar totais das tabelas e as execuções do Kestra
  const isKestraConfigured = !!process.env.KESTRA_WEBHOOK_URL
  
  const [
    { count: totalClientes }, 
    { count: totalVendas }, 
    { count: totalEstoque }, 
    { count: totalVendedores },
    executions
  ] = await Promise.all([
    supabase.from('gigatech_clientes_config').select('*', { count: 'exact', head: true }).eq('ativo', true),
    supabase.from('gigatech_vendas').select('*', { count: 'exact', head: true }),
    supabase.from('gigatech_estoque').select('*', { count: 'exact', head: true }),
    supabase.from('gigatech_vendedores').select('*', { count: 'exact', head: true }),
    isKestraConfigured ? getKestraExecutions() : Promise.resolve([])
  ])

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-bold tracking-tight">Overview</h2>
          <p className="text-muted-foreground text-sm">Acompanhe o volume de processamento do robô da Giga Tech.</p>
        </div>
        <RefreshButton />
      </div>


      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Clientes Ativos</CardTitle>
            <Users className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalClientes || 0}</div>
          </CardContent>
        </Card>
        
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Vendas Processadas</CardTitle>
            <ShoppingCart className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalVendas?.toLocaleString('pt-BR') || 0}</div>
          </CardContent>
        </Card>
        
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Registros de Estoque</CardTitle>
            <Package className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalEstoque?.toLocaleString('pt-BR') || 0}</div>
          </CardContent>
        </Card>
        
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Vendas por Vendedores</CardTitle>
            <UsersRound className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalVendedores?.toLocaleString('pt-BR') || 0}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-1">
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white min-h-[400px]">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Tempos de Processamento</CardTitle>
            <p className="text-xs text-muted-foreground">
              Duração e status das últimas execuções de sincronização do robô.
            </p>
          </CardHeader>
          <CardContent className="min-h-[300px] flex items-center justify-center pt-4">
            {!isKestraConfigured ? (
              <div className="flex items-center gap-2 text-sm text-rose-500 font-mono">
                <AlertCircle className="h-4 w-4" />
                <span>Kestra não configurado no servidor.</span>
              </div>
            ) : (
              <ProcessChart executions={executions} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

