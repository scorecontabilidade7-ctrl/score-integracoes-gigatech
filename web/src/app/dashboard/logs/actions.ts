'use server'

import { getKestraLogs, getKestraExecutions } from '@/utils/kestra'

export async function fetchKestraLogsAction(executionId: string) {
  try {
    const logs = await getKestraLogs(executionId)
    return { success: true, logs }
  } catch (err: any) {
    return { success: false, error: err.message || 'Erro ao carregar logs' }
  }
}

export async function fetchKestraExecutionsAction(systemId: string = 'gigatech') {
  try {
    const executions = await getKestraExecutions(systemId)
    return { success: true, executions }
  } catch (err: any) {
    return { success: false, error: err.message || 'Erro ao carregar execuções' }
  }
}

