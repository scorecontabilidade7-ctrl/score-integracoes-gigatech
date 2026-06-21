import { getKestraExecutions } from '@/utils/kestra'
import LogsTable from '@/components/logs-table'
import { AlertCircle } from 'lucide-react'
import { SYSTEMS } from '@/utils/systems'
import { redirect } from 'next/navigation'

export const dynamic = 'force-dynamic'

interface PageProps {
  params: Promise<{ system: string }>
}

export default async function LogsPage({ params }: PageProps) {
  const { system } = await params
  const systemConfig = SYSTEMS[system]

  if (!systemConfig) {
    redirect('/dashboard')
  }

  const isConfigured = !!process.env.KESTRA_WEBHOOK_URL
  const executions = isConfigured ? await getKestraExecutions(system) : []

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-2xl font-bold tracking-tight">Histórico de Execuções ({systemConfig.name})</h2>
        <p className="text-muted-foreground text-sm">
          Acompanhe o status, durações e console de logs das execuções disparadas no Kestra.
        </p>
      </div>

      {!isConfigured ? (
        <div className="flex items-center gap-3 p-4 rounded-2xl border border-rose-200 bg-rose-50 text-rose-700">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <div className="text-sm">
            <strong>Kestra não configurado:</strong> A variável de ambiente <code>KESTRA_WEBHOOK_URL</code> não foi encontrada nas configurações do servidor.
          </div>
        </div>
      ) : (
        <LogsTable initialExecutions={executions} systemId={system} />
      )}
    </div>
  )
}
