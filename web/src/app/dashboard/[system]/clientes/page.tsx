import { createClient } from '@/utils/supabase/server'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { TriggerWebhookDialog } from '@/components/trigger-webhook-dialog'
import { NewClientDialog } from '@/components/new-client-dialog'
import { EditClientDialog } from '@/components/edit-client-dialog'
import { SYSTEMS } from '@/utils/systems'
import { redirect } from 'next/navigation'

export const dynamic = 'force-dynamic'

interface PageProps {
  params: Promise<{ system: string }>
}

export default async function ClientesPage({ params }: PageProps) {
  const { system } = await params
  const systemConfig = SYSTEMS[system]

  if (!systemConfig) {
    redirect('/dashboard')
  }

  const supabase = await createClient()

  // Buscar clientes específicos deste sistema
  const { data: clientes } = await supabase
    .from(systemConfig.configTable)
    .select('*')
    .order('nome_loja', { ascending: true })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-bold tracking-tight">Gestão de Clientes ({systemConfig.name})</h2>
          <p className="text-muted-foreground text-sm">Gerencie as lojas cadastradas e dispare processamentos retroativos.</p>
        </div>
        <NewClientDialog systemId={system} />
      </div>

      <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl overflow-hidden">
        <CardContent className="p-0">
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead className="font-semibold text-foreground py-4 pl-6">Nome da Loja</TableHead>
                <TableHead className="font-semibold text-foreground py-4">E-mail de Login</TableHead>
                <TableHead className="font-semibold text-foreground py-4">Status</TableHead>
                <TableHead className="text-right font-semibold text-foreground py-4 pr-6">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {clientes && clientes.length > 0 ? (
                clientes.map((cliente) => {
                  const emailVal = cliente[systemConfig.emailField] || ""
                  
                  return (
                    <TableRow key={cliente.id} className="hover:bg-muted/30">
                      <TableCell className="font-medium pl-6">{cliente.nome_loja}</TableCell>
                      <TableCell className="text-muted-foreground font-data text-sm">{emailVal}</TableCell>
                      <TableCell>
                        {cliente.ativo ? (
                          <Badge variant="outline" className="bg-emerald-50 text-emerald-600 border-emerald-200 rounded-md px-2 py-0.5">
                            Ativo
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="bg-muted text-muted-foreground rounded-md px-2 py-0.5">
                            Inativo
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right pr-6 flex items-center justify-end gap-2">
                        <EditClientDialog cliente={cliente} systemId={system} />
                        {cliente.ativo ? (
                          <TriggerWebhookDialog clienteId={cliente.id} clienteNome={cliente.nome_loja} systemId={system} />
                        ) : (
                          <span className="text-xs text-muted-foreground">Inativo</span>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center text-muted-foreground pl-6 pr-6">
                    Nenhum cliente cadastrado para {systemConfig.name}.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
