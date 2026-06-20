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
import { PlayCircle, Clock, CheckCircle2, XCircle } from "lucide-react"

export default async function LogsPage() {
  // Placeholder data for now
  const logs = [
    {
      id: "log-001",
      cliente: "LF Store",
      fluxo: "Extração Diária",
      status: "Sucesso",
      tempo: "2m 14s",
      data: "20/06/2026 13:40",
    },
    {
      id: "log-002",
      cliente: "LF Store",
      fluxo: "Processamento Retroativo",
      status: "Em Execução",
      tempo: "4m 02s",
      data: "20/06/2026 13:35",
    },
    {
      id: "log-003",
      cliente: "LF Store",
      fluxo: "Extração Diária",
      status: "Falha",
      tempo: "14s",
      data: "19/06/2026 13:40",
    }
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-bold tracking-tight">Histórico de Execuções (Logs)</h2>
          <p className="text-muted-foreground text-sm">
            Acompanhe o status e os logs das execuções disparadas no Kestra.
          </p>
        </div>
      </div>

      <Card className="border-0 shadow-sm shadow-black/5 rounded-2xl overflow-hidden">
        <CardContent className="p-0">
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead className="font-semibold text-foreground py-4">Cliente</TableHead>
                <TableHead className="font-semibold text-foreground py-4">Fluxo</TableHead>
                <TableHead className="font-semibold text-foreground py-4">Data/Hora</TableHead>
                <TableHead className="font-semibold text-foreground py-4">Duração</TableHead>
                <TableHead className="text-right font-semibold text-foreground py-4">Status</TableHead>
              </TableRow>
            </TableHeader>
          <TableBody>
            {logs.map((log) => (
              <TableRow key={log.id} className="hover:bg-muted/30">
                <TableCell className="font-medium">
                  {log.cliente}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <PlayCircle className="h-4 w-4 text-muted-foreground/50" />
                    {log.fluxo}
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground font-data text-sm">
                  {log.data}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  <div className="flex items-center gap-2 font-data text-sm">
                    <Clock className="h-3 w-3 text-muted-foreground/50" />
                    {log.tempo}
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  {log.status === "Sucesso" && (
                    <Badge variant="outline" className="bg-emerald-50 text-emerald-600 border-emerald-200 gap-1.5 px-2.5 py-1">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Sucesso
                    </Badge>
                  )}
                  {log.status === "Em Execução" && (
                    <Badge variant="outline" className="bg-blue-50 text-blue-600 border-blue-200 gap-1.5 px-2.5 py-1">
                      <div className="h-3 w-3 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
                      Rodando
                    </Badge>
                  )}
                  {log.status === "Falha" && (
                    <Badge variant="outline" className="bg-rose-50 text-rose-600 border-rose-200 gap-1.5 px-2.5 py-1">
                      <XCircle className="h-3.5 w-3.5" />
                      Falha
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
            
            {logs.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  Nenhuma execução registrada.
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
