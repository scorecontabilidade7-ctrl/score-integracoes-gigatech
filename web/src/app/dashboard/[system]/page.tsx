import { createClient } from '@/utils/supabase/server'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Users, PlayCircle, Clock, CheckCircle2, AlertCircle } from 'lucide-react'
import { getKestraExecutions } from '@/utils/kestra'
import { SYSTEMS } from '@/utils/systems'
import ProcessChart from '@/components/process-chart'
import RefreshButton from '@/components/refresh-button'
import { redirect } from 'next/navigation'

export const dynamic = 'force-dynamic'

interface PageProps {
  params: Promise<{ system: string }>
}

export default async function DashboardOverview({ params }: PageProps) {
  const { system } = await params
  const systemConfig = SYSTEMS[system]

  if (!systemConfig) {
    redirect('/dashboard')
  }

  const isKestraConfigured = !!process.env.KESTRA_WEBHOOK_URL
  const supabase = await createClient()

  // Buscar clientes ativos e execuções do Kestra
  const [
    { count: totalClientes },
    executions
  ] = await Promise.all([
    supabase.from(systemConfig.configTable).select('*', { count: 'exact', head: true }).eq('ativo', true),
    isKestraConfigured ? getKestraExecutions(system) : Promise.resolve([])
  ])

  // Calcular métricas adicionais do Kestra
  const totalExecucoes = executions.length
  
  const completedExecs = executions.filter(e => e.status === 'Sucesso' || e.status === 'Falha')
  
  const avgDurationSeconds = completedExecs.length > 0
    ? Math.round(completedExecs.reduce((acc, curr) => acc + curr.durationSeconds, 0) / completedExecs.length)
    : 0
  
  const formattedAvgDuration = avgDurationSeconds > 60
    ? `${Math.floor(avgDurationSeconds / 60)}m ${avgDurationSeconds % 60}s`
    : `${avgDurationSeconds}s`

  const successCount = executions.filter(e => e.status === 'Sucesso').length
  const successRate = completedExecs.length > 0
    ? Math.round((successCount / completedExecs.length) * 100)
    : 100

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-bold tracking-tight">Overview ({systemConfig.name})</h2>
          <p className="text-muted-foreground text-sm">Acompanhe o volume de processamento e a performance da automação.</p>
        </div>
        <RefreshButton />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: Clientes Ativos */}
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Clientes Ativos</CardTitle>
            <Users className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalClientes || 0}</div>
          </CardContent>
        </Card>
        
        {/* Card 2: Total de Execuções */}
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total de Execuções</CardTitle>
            <PlayCircle className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{totalExecucoes || 0}</div>
          </CardContent>
        </Card>
        
        {/* Card 3: Tempo Médio de Execução */}
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Duração Média</CardTitle>
            <Clock className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{formattedAvgDuration}</div>
          </CardContent>
        </Card>
        
        {/* Card 4: Taxa de Sucesso */}
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Taxa de Sucesso</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-data">{successRate}%</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-1">
        <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl bg-white min-h-[400px]">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Histórico de Processamento</CardTitle>
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
