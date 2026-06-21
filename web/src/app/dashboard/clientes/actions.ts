'use server'

import { revalidatePath } from 'next/cache'
import { createClient } from '@/utils/supabase/server'
import { SYSTEMS } from '@/utils/systems'

export async function createCliente(formData: FormData, systemId: string) {
  const systemConfig = SYSTEMS[systemId]
  if (!systemConfig) {
    return { error: `Sistema '${systemId}' inválido.` }
  }

  const supabase = await createClient()
  
  const nome_loja = formData.get('nome') as string
  const email = formData.get('email') as string
  const senha = formData.get('senha') as string
  const ativo = formData.get('ativo') === 'true'
  
  if (!nome_loja || !email || !senha) {
    return { error: 'Nome, e-mail e senha são obrigatórios.' }
  }

  const { error } = await supabase
    .from(systemConfig.configTable)
    .insert([{
      nome_loja,
      [systemConfig.emailField]: email,
      [systemConfig.passwordField]: senha,
      ativo
    }])

  if (error) {
    if (error.code === '23505') {
      return { error: 'Este e-mail já está cadastrado.' }
    }
    console.error("Erro ao cadastrar cliente:", error)
    return { error: 'Erro ao cadastrar o cliente. Verifique as configurações.' }
  }

  revalidatePath(`/dashboard/${systemId}/clientes`)
  return { success: true }
}

export async function updateCliente(formData: FormData, systemId: string) {
  const systemConfig = SYSTEMS[systemId]
  if (!systemConfig) {
    return { error: `Sistema '${systemId}' inválido.` }
  }

  const supabase = await createClient()
  
  const id = formData.get('id') as string
  const nome_loja = formData.get('nome') as string
  const email = formData.get('email') as string
  const senha = formData.get('senha') as string
  const ativo = formData.get('ativo') === 'true'
  
  if (!id || !nome_loja || !email || !senha) {
    return { error: 'Todos os campos são obrigatórios para edição.' }
  }

  const { error } = await supabase
    .from(systemConfig.configTable)
    .update({
      nome_loja,
      [systemConfig.emailField]: email,
      [systemConfig.passwordField]: senha,
      ativo
    })
    .eq('id', id)

  if (error) {
    if (error.code === '23505') {
      return { error: 'Este e-mail já está cadastrado por outro cliente.' }
    }
    console.error("Erro ao atualizar cliente:", error)
    return { error: 'Erro ao atualizar o cliente.' }
  }

  revalidatePath(`/dashboard/${systemId}/clientes`)
  return { success: true }
}

export async function triggerKestraFlow(clienteId: string, dataInicial: string, dataFinal: string, systemId: string) {
  const systemConfig = SYSTEMS[systemId]
  if (!systemConfig) {
    return { error: `Sistema '${systemId}' inválido.` }
  }

  const url = process.env.KESTRA_WEBHOOK_URL
  if (!url) {
    return { error: 'A URL do Webhook do Kestra não está configurada no servidor (KESTRA_WEBHOOK_URL).' }
  }

  // Parse da URL do webhook para obter a base URL do Kestra
  // Ex: https://www.kestra.scoreconsultoria.com.br/api/v1/main/executions/webhook/gigatech.automacoes/gigatech_to_supabase/GIGATECH_EXTRACT_KEY
  const match = url.match(/^(https?:\/\/[^\/]+(?:\/[^\/]+)*)\/executions\/webhook\/([^\/]+)\/([^\/]+)\/([^\/]+)/)
  if (!match) {
    return { error: 'A URL do Webhook do Kestra está em um formato inválido para parser.' }
  }

  const baseUrl = match[1]
  const targetUrl = `${baseUrl}/executions/webhook/${systemConfig.namespace}/${systemConfig.flowId}/${systemConfig.webhookKey}`

  try {
    const response = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        cliente_id: clienteId,
        data_inicial: dataInicial,
        data_final: dataFinal
      })
    })

    if (!response.ok) {
      throw new Error(`O Kestra retornou erro status ${response.status}`)
    }

    return { success: true }
  } catch (err: any) {
    console.error("Erro ao acionar webhook do Kestra:", err)
    return { error: err.message || 'Erro de rede ou conexão com o Kestra.' }
  }
}
