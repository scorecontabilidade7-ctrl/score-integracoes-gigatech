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
