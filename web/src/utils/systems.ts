export interface SystemConfig {
  id: string
  name: string
  namespace: string
  flowId: string
  webhookKey: string
  configTable: string
  emailField: string
  passwordField: string
  iconName: 'database' | 'activity'
  description: string
}

export const SYSTEMS: Record<string, SystemConfig> = {
  gigatech: {
    id: 'gigatech',
    name: 'Giga Tech',
    namespace: 'gigatech.automacoes',
    flowId: 'gigatech_to_supabase',
    webhookKey: 'GIGATECH_EXTRACT_KEY',
    configTable: 'gigatech_clientes_config',
    emailField: 'email_login_giga',
    passwordField: 'senha_login_giga',
    iconName: 'database',
    description: 'Automação de Relatórios de Vendas, Estoque e Vendedores no ERP Giga Tech.'
  },
  clinicorp: {
    id: 'clinicorp',
    name: 'Clinicorp',
    namespace: 'clinicorp.automacoes',
    flowId: 'clinicorp_to_supabase',
    webhookKey: 'CLINICORP_EXTRACT_KEY',
    configTable: 'clinicorp_clientes_config',
    emailField: 'email_login_clinicorp',
    passwordField: 'senha_login_clinicorp',
    iconName: 'activity',
    description: 'Automação Odontológica: Faturamento por Profissional, Orçamentos e Consultas.'
  }
}
