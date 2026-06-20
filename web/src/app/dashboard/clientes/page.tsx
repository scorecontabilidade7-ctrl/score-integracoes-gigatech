import { createClient } from '@/utils/supabase/server'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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

export default async function ClientesPage() {
  const supabase = await createClient()

  // Buscar clientes do banco
  const { data: clientes, error } = await supabase
    .from('gigatech_clientes_config')
    .select('*')
    .order('nome_loja', { ascending: true })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-bold tracking-tight">Gestão de Clientes</h2>
          <p className="text-muted-foreground text-sm">Gerencie as lojas cadastradas e dispare processamentos retroativos.</p>
        </div>
        <NewClientDialog />
      </div>

      <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl overflow-hidden">
        <CardContent className="p-0">
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead className="font-semibold text-foreground py-4">Nome da Loja</TableHead>
                <TableHead className="font-semibold text-foreground py-4">E-mail de Login</TableHead>
                <TableHead className="font-semibold text-foreground py-4">Status</TableHead>
                <TableHead className="text-right font-semibold text-foreground py-4">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {clientes && clientes.length > 0 ? (
                clientes.map((cliente) => (
                  <TableRow key={cliente.id} className="hover:bg-muted/30">
                    <TableCell className="font-medium">{cliente.nome_loja}</TableCell>
                    <TableCell className="text-muted-foreground">{cliente.email_login_giga}</TableCell>
                    <TableCell>
                      {cliente.ativo ? (
                        <Badge variant="outline" className="bg-primary/10 text-primary hover:bg-primary/20 border-primary/20 rounded-md">
                          Ativo
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-muted text-muted-foreground rounded-md">
                          Inativo
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right flex items-center justify-end gap-2">
                      <EditClientDialog cliente={cliente} />
                      {cliente.ativo ? (
                        <TriggerWebhookDialog clienteId={cliente.id} clienteNome={cliente.nome_loja} />
                      ) : (
                        <span className="text-xs text-muted-foreground">Inativo</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                    Nenhum cliente cadastrado.
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
