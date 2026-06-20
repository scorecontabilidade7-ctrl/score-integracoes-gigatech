'use server'

import { revalidatePath } from 'next/cache'
import { createClient } from '@/utils/supabase/server'

export async function createCliente(formData: FormData) {
  const supabase = await createClient()
  
  const nome_loja = formData.get('nome') as string
  const email_login_giga = formData.get('email') as string
  const senha_login_giga = formData.get('senha') as string
  const ativo = formData.get('ativo') === 'true'
  
  if (!nome_loja || !email_login_giga || !senha_login_giga) {
    return { error: 'Nome, e-mail e senha são obrigatórios.' }
  }

  const { error } = await supabase
    .from('gigatech_clientes_config')
    .insert([{ nome_loja, email_login_giga, senha_login_giga, ativo }])

  if (error) {
    if (error.code === '23505') {
      return { error: 'Este e-mail já está cadastrado.' }
    }
    return { error: 'Erro ao cadastrar o cliente. Verifique se a tabela existe.' }
  }

  revalidatePath('/dashboard/clientes')
  return { success: true }
}

export async function updateCliente(formData: FormData) {
  const supabase = await createClient()
  
  const id = formData.get('id') as string
  const nome_loja = formData.get('nome') as string
  const email_login_giga = formData.get('email') as string
  const senha_login_giga = formData.get('senha') as string
  const ativo = formData.get('ativo') === 'true'
  
  if (!id || !nome_loja || !email_login_giga || !senha_login_giga) {
    return { error: 'Todos os campos são obrigatórios para edição.' }
  }

  const { error } = await supabase
    .from('gigatech_clientes_config')
    .update({ nome_loja, email_login_giga, senha_login_giga, ativo })
    .eq('id', id)

  if (error) {
    if (error.code === '23505') {
      return { error: 'Este e-mail já está cadastrado por outro cliente.' }
    }
    return { error: 'Erro ao atualizar o cliente.' }
  }

  revalidatePath('/dashboard/clientes')
  return { success: true }
}

export async function triggerKestraFlow(clienteId: string, dataInicial: string, dataFinal: string) {
  const url = process.env.KESTRA_WEBHOOK_URL
  if (!url) {
    return { error: 'A URL do Webhook do Kestra não está configurada no servidor (KESTRA_WEBHOOK_URL).' }
  }

  try {
    const response = await fetch(url, {
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

