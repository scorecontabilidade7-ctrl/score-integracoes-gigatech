import { createClient } from '@/utils/supabase/server'

export interface KestraExecution {
  id: string
  cliente: string
  clienteId: string
  fluxo: string
  status: 'Sucesso' | 'Em Execução' | 'Falha' | 'Pausado'
  tempo: string
  data: string
  kestraUrl: string
  originalState: string
  durationSeconds: number
}

interface KestraRawExecution {
  id: string
  namespace: string
  flowId: string
  state: {
    current: string
    startDate: string
    endDate?: string
    duration?: string
  }
  inputs?: {
    cliente_id?: string
    data_inicial?: string
    data_final?: string
  }
  trigger?: {
    id: string
    type: string
    variables?: {
      body?: {
        cliente_id?: string
        data_inicial?: string
        data_final?: string
      }
    }
  }
}

export async function getKestraExecutions(): Promise<KestraExecution[]> {
  const webhookUrl = process.env.KESTRA_WEBHOOK_URL || ''
  if (!webhookUrl) {
    console.warn("KESTRA_WEBHOOK_URL não configurado.")
    return []
  }

  // Parse da URL do webhook para obter base URL, namespace e flowId
  // Ex: https://www.kestra.scoreconsultoria.com.br/api/v1/main/executions/webhook/gigatech.automacoes/gigatech_to_supabase/GIGATECH_EXTRACT_KEY
  const match = webhookUrl.match(/^(https?:\/\/[^\/]+(?:\/[^\/]+)*)\/executions\/webhook\/([^\/]+)\/([^\/]+)/)
  if (!match) {
    console.warn("KESTRA_WEBHOOK_URL no formato inválido para parser:", webhookUrl)
    return []
  }

  const baseUrl = match[1]
  const namespace = match[2]
  const flowId = match[3]

  const searchUrl = `${baseUrl}/executions/search?namespace=${namespace}&flowId=${flowId}&size=50`

  try {
    const headers: Record<string, string> = {
      'Accept': 'application/json',
    }

    if (process.env.KESTRA_API_TOKEN) {
      headers['Authorization'] = `Bearer ${process.env.KESTRA_API_TOKEN}`
    } else if (process.env.KESTRA_BASIC_AUTH) {
      headers['Authorization'] = `Basic ${Buffer.from(process.env.KESTRA_BASIC_AUTH).toString('base64')}`
    }

    const res = await fetch(searchUrl, {
      headers,
      next: { revalidate: 15 } // Cache de 15 segundos
    })

    if (!res.ok) {
      throw new Error(`Erro ao buscar execuções do Kestra: ${res.status}`)
    }

    const data = await res.json()
    const rawExecutions: KestraRawExecution[] = data.results || []

    const executions = [...rawExecutions].sort((a, b) => {
      const timeA = a.state?.startDate ? new Date(a.state.startDate).getTime() : 0
      const timeB = b.state?.startDate ? new Date(b.state.startDate).getTime() : 0
      return timeB - timeA
    })

    // Buscar clientes ativos no Supabase para mapeamento de cliente_id -> nome_loja
    const supabase = await createClient()
    const { data: clientes } = await supabase
      .from('gigatech_clientes_config')
      .select('id, nome_loja')

    const clientMap = new Map<string, string>()
    clientes?.forEach(c => {
      clientMap.set(c.id, c.nome_loja)
    })

    const uiBaseUrl = baseUrl.replace('/api/v1', '/ui')

    return executions.map(exec => {
      // Tenta obter o cliente_id dos inputs ou do payload do trigger (webhook)
      let clienteId = exec.inputs?.cliente_id || exec.trigger?.variables?.body?.cliente_id || ''
      
      // Se for disparado pelo agendador de hora em hora e não tiver cliente_id explícito, assume TODOS
      if (!clienteId && exec.trigger?.id === 'hourly_schedule') {
        clienteId = 'TODOS'
      }

      const clienteNome = (!clienteId || clienteId.toUpperCase() === 'TODOS')
        ? 'Todos os Clientes'
        : (clientMap.get(clienteId) || `Cliente (${clienteId.substring(0, 8)}...)`)

      // Data/Hora formatada em fuso local do Brasil
      let dataStr = 'N/A'
      if (exec.state.startDate) {
        const dt = new Date(exec.state.startDate)
        dataStr = dt.toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' })
      }

      // Cálculo de duração em segundos e string amigável
      let durationSeconds = 0
      let tempoStr = '-'
      if (exec.state.startDate && exec.state.endDate) {
        const diffMs = new Date(exec.state.endDate).getTime() - new Date(exec.state.startDate).getTime()
        durationSeconds = Math.max(0, Math.floor(diffMs / 1000))
      } else if (exec.state.startDate) {
        const diffMs = Date.now() - new Date(exec.state.startDate).getTime()
        durationSeconds = Math.max(0, Math.floor(diffMs / 1000))
      }

      if (durationSeconds > 0) {
        const mins = Math.floor(durationSeconds / 60)
        const secs = durationSeconds % 60
        tempoStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`
      }

      // Mapear status Kestra -> badges do dashboard
      let statusFormat: 'Sucesso' | 'Em Execução' | 'Falha' | 'Pausado' = 'Falha'
      const rawState = exec.state.current
      if (rawState === 'SUCCESS') {
        statusFormat = 'Sucesso'
      } else if (['RUNNING', 'CREATED', 'RESTARTED'].includes(rawState)) {
        statusFormat = 'Em Execução'
      } else if (rawState === 'PAUSED') {
        statusFormat = 'Pausado'
      }

      // Formatar nome do fluxo amigável
      const dataInicial = exec.inputs?.data_inicial || exec.trigger?.variables?.body?.data_inicial || ''
      const dataFinal = exec.inputs?.data_final || exec.trigger?.variables?.body?.data_final || ''
      
      let fluxoNome = 'Sincronização Diária (D-1)'
      if (dataInicial || dataFinal) {
        fluxoNome = `Retroativo (${dataInicial} a ${dataFinal})`
      }

      return {
        id: exec.id,
        cliente: clienteNome,
        clienteId: clienteId,
        fluxo: fluxoNome,
        status: statusFormat,
        tempo: tempoStr,
        data: dataStr,
        kestraUrl: `${uiBaseUrl}/executions/${namespace}/${flowId}/${exec.id}/logs`,
        originalState: rawState,
        durationSeconds
      }
    })

  } catch (err) {
    console.error("Erro no getKestraExecutions:", err)
    return []
  }
}

export async function getKestraLogs(executionId: string) {
  const webhookUrl = process.env.KESTRA_WEBHOOK_URL || ''
  if (!webhookUrl) return []

  const match = webhookUrl.match(/^(https?:\/\/[^\/]+(?:\/[^\/]+)*)\/executions\/webhook\/([^\/]+)\/([^\/]+)/)
  if (!match) return []

  const baseUrl = match[1]
  const logsUrl = `${baseUrl}/logs/${executionId}`

  try {
    const headers: Record<string, string> = {
      'Accept': 'application/json',
    }

    if (process.env.KESTRA_API_TOKEN) {
      headers['Authorization'] = `Bearer ${process.env.KESTRA_API_TOKEN}`
    } else if (process.env.KESTRA_BASIC_AUTH) {
      headers['Authorization'] = `Basic ${Buffer.from(process.env.KESTRA_BASIC_AUTH).toString('base64')}`
    }

    const res = await fetch(logsUrl, { headers })
    if (!res.ok) {
      throw new Error(`Erro ao buscar logs da execução ${executionId}: ${res.status}`)
    }

    const logs = await res.json()
    
    const mappedLogs = logs.map((log: any) => ({
      timestamp: log.timestamp ? new Date(log.timestamp).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' }) : '',
      timestampRaw: log.timestamp || '',
      level: log.level || 'INFO',
      message: log.message || '',
      taskId: log.taskId || ''
    }))

    // Ordena do mais recente para o mais antigo
    return mappedLogs.sort((a: any, b: any) => {
      const timeA = a.timestampRaw ? new Date(a.timestampRaw).getTime() : 0
      const timeB = b.timestampRaw ? new Date(b.timestampRaw).getTime() : 0
      return timeB - timeA
    })
  } catch (err) {
    console.error("Erro no getKestraLogs:", err)
    return []
  }
}
