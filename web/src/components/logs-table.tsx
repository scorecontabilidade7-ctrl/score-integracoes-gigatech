'use client'

import { useState, useEffect, useRef } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { 
  Sheet, 
  SheetContent, 
  SheetHeader, 
  SheetTitle, 
  SheetDescription 
} from "@/components/ui/sheet"
import { 
  PlayCircle, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  ExternalLink, 
  FileText, 
  AlertCircle,
  Terminal
} from "lucide-react"
import { fetchKestraLogsAction, fetchKestraExecutionsAction } from "@/app/dashboard/logs/actions"
import { KestraExecution } from "@/utils/kestra"

interface LogsTableProps {
  initialExecutions: KestraExecution[]
}

interface LogEntry {
  timestamp: string
  level: string
  message: string
  taskId: string
}

export default function LogsTable({ initialExecutions }: LogsTableProps) {
  const [executions, setExecutions] = useState<KestraExecution[]>(initialExecutions)
  const [selectedExec, setSelectedExec] = useState<KestraExecution | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loadingLogs, setLoadingLogs] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  // Paginação de 10 em 10
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 10
  const totalPages = Math.ceil(executions.length / itemsPerPage) || 1
  const startIndex = (currentPage - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const paginatedExecutions = executions.slice(startIndex, endIndex)

  // Ajusta a página atual se a lista for atualizada e encolher
  useEffect(() => {
    const maxPage = Math.ceil(executions.length / itemsPerPage) || 1
    if (currentPage > maxPage) {
      setCurrentPage(maxPage)
    }
  }, [executions])

  // Polling em tempo real se houver alguma execução rodando na lista
  useEffect(() => {
    const hasRunningExec = executions.some(e => e.status === 'Em Execução')
    if (!hasRunningExec) return

    const pollExecutions = async () => {
      try {
        const res = await fetchKestraExecutionsAction()
        if (res.success && res.executions) {
          setExecutions(res.executions)
        }
      } catch (e) {
        console.error("Erro ao atualizar lista de execuções:", e)
      }
    }

    const intervalId = setInterval(pollExecutions, 4000)
    return () => clearInterval(intervalId)
  }, [executions])

  // Polling dos logs no console em tempo real se a execução ativa estiver rodando
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null

    if (sheetOpen && selectedExec) {
      // Verifica se a execução selecionada ainda está rodando na lista atualizada
      const currentExec = executions.find(e => e.id === selectedExec.id)
      const isRunning = currentExec 
        ? currentExec.status === 'Em Execução'
        : (selectedExec.status === 'Em Execução' || selectedExec.originalState === 'RUNNING')

      if (isRunning) {
        const pollLogs = async () => {
          try {
            const res = await fetchKestraLogsAction(selectedExec.id)
            if (res.success && res.logs) {
              setLogs(res.logs)
            }
          } catch (e) {
            console.error("Erro no polling de logs do Kestra:", e)
          }
        }

        // Atualiza os logs a cada 2.5 segundos
        intervalId = setInterval(pollLogs, 2500)
      }
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId)
      }
    }
  }, [sheetOpen, selectedExec, executions])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      // Recarregar a página chamando a rota ou re-fetching
      window.location.reload()
    } catch (e) {
      console.error(e)
    } finally {
      setRefreshing(false)
    }
  }

  const handleOpenLogs = async (exec: KestraExecution) => {
    setSelectedExec(exec)
    setLogs([])
    setLoadingLogs(true)
    setSheetOpen(true)
    
    try {
      const res = await fetchKestraLogsAction(exec.id)
      if (res.success && res.logs) {
        setLogs(res.logs)
      } else {
        console.error(res.error)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingLogs(false)
    }
  }

  const getLogLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case 'ERROR':
      case 'FAIL':
      case 'CRITICAL':
        return 'text-rose-400 font-semibold'
      case 'WARN':
      case 'WARNING':
        return 'text-amber-400 font-semibold'
      case 'DEBUG':
      case 'TRACE':
        return 'text-zinc-500'
      default:
        return 'text-zinc-300'
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <span className="text-sm text-muted-foreground">
          Mostrando as últimas {executions.length} execuções
        </span>
        <Button 
          variant="outline" 
          size="sm" 
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded-xl border-black/5 hover:bg-black/[0.02]"
        >
          <Clock className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Atualizar Lista
        </Button>
      </div>

      <div className="border border-black/5 shadow-sm shadow-black/5 rounded-2xl overflow-hidden bg-white">
        <Table>
          <TableHeader className="bg-muted/50">
            <TableRow>
              <TableHead className="font-semibold text-foreground py-4 pl-6">Cliente / Escopo</TableHead>
              <TableHead className="font-semibold text-foreground py-4">Tipo de Fluxo</TableHead>
              <TableHead className="font-semibold text-foreground py-4">Data/Hora Início</TableHead>
              <TableHead className="font-semibold text-foreground py-4">Duração</TableHead>
              <TableHead className="font-semibold text-foreground py-4">Status</TableHead>
              <TableHead className="text-right font-semibold text-foreground py-4 pr-6">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedExecutions.map((exec) => (
              <TableRow key={exec.id} className="hover:bg-muted/30">
                <TableCell className="font-medium pl-6">
                  {exec.cliente}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <PlayCircle className="h-4 w-4 text-muted-foreground/50" />
                    {exec.fluxo}
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground font-data text-sm">
                  {exec.data}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  <div className="flex items-center gap-2 font-data text-sm">
                    <Clock className="h-3 w-3 text-muted-foreground/50" />
                    {exec.tempo}
                  </div>
                </TableCell>
                <TableCell>
                  {exec.status === "Sucesso" && (
                    <Badge variant="outline" className="bg-emerald-50 text-emerald-600 border-emerald-200 gap-1.5 px-2.5 py-1 rounded-full">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Sucesso
                    </Badge>
                  )}
                  {exec.status === "Em Execução" && (
                    <Badge variant="outline" className="bg-blue-50 text-blue-600 border-blue-200 gap-1.5 px-2.5 py-1 rounded-full">
                      <div className="h-3 w-3 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
                      Rodando
                    </Badge>
                  )}
                  {exec.status === "Falha" && (
                    <Badge variant="outline" className="bg-rose-50 text-rose-600 border-rose-200 gap-1.5 px-2.5 py-1 rounded-full">
                      <XCircle className="h-3.5 w-3.5" />
                      Falha
                    </Badge>
                  )}
                  {exec.status === "Pausado" && (
                    <Badge variant="outline" className="bg-amber-50 text-amber-600 border-amber-200 gap-1.5 px-2.5 py-1 rounded-full">
                      <AlertCircle className="h-3.5 w-3.5" />
                      Pausado
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-right pr-6">
                  <div className="flex justify-end items-center gap-2">
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => handleOpenLogs(exec)}
                      className="h-8 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium gap-1.5 border-0 shadow-sm"
                    >
                      <Terminal className="h-3.5 w-3.5" />
                      Console
                    </Button>
                    <a
                      href={exec.kestraUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Abrir Execução no Kestra"
                      className={cn(
                        buttonVariants({ variant: "ghost", size: "icon" }),
                        "h-8 w-8 rounded-lg hover:bg-black/5"
                      )}
                    >
                      <ExternalLink className="h-4 w-4 text-muted-foreground" />
                    </a>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            
            {paginatedExecutions.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center text-muted-foreground pl-6 pr-6">
                  Nenhuma execução registrada no Kestra ou erro de conexão.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Paginação */}
      {totalPages > 1 && (
        <div className="flex justify-between items-center py-2 px-1">
          <span className="text-xs text-muted-foreground">
            Mostrando {startIndex + 1} a {Math.min(endIndex, executions.length)} de {executions.length} execuções
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
              disabled={currentPage === 1}
              className="rounded-xl border-black/5 hover:bg-black/[0.02]"
            >
              Anterior
            </Button>
            <span className="text-xs font-medium text-foreground px-2">
              Página {currentPage} de {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
              disabled={currentPage === totalPages}
              className="rounded-xl border-black/5 hover:bg-black/[0.02]"
            >
              Próximo
            </Button>
          </div>
        </div>
      )}

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="w-full sm:max-w-4xl data-[side=right]:sm:max-w-4xl bg-zinc-950 text-zinc-100 border-zinc-800 p-0 flex flex-col h-full">
          <div className="p-6 border-b border-zinc-800 bg-zinc-900/50">
            <SheetHeader className="space-y-1">
              <div className="flex items-center gap-2 text-zinc-400 text-xs font-mono uppercase tracking-wider mb-1">
                <Terminal className="h-3.5 w-3.5 text-primary" />
                Console de Execução
              </div>
              <SheetTitle className="text-lg font-bold text-zinc-50 flex items-center justify-between">
                <span>{selectedExec?.cliente}</span>
                <span className="text-xs font-mono px-2 py-0.5 bg-zinc-800 text-zinc-400 rounded">
                  ID: {selectedExec?.id}
                </span>
              </SheetTitle>
              <SheetDescription className="text-zinc-400 text-xs font-mono">
                Fluxo: {selectedExec?.fluxo} | Status: {selectedExec?.originalState}
              </SheetDescription>
            </SheetHeader>
          </div>

          {/* Área do terminal de logs */}
          <div className="flex-1 overflow-y-auto p-6 font-mono text-[11px] leading-relaxed bg-zinc-950 selection:bg-zinc-800">
            {loadingLogs ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-zinc-500">
                <div className="h-5 w-5 rounded-full border-2 border-zinc-700 border-t-zinc-300 animate-spin" />
                Carregando logs do Kestra...
              </div>
            ) : logs.length > 0 ? (
              <div className="space-y-1">
                {logs.map((log, idx) => (
                  <div key={idx} className="hover:bg-zinc-900/50 py-0.5 rounded px-1 transition-colors flex items-start gap-2">
                    <span className="text-zinc-600 select-none text-[10px] pt-0.5 w-[65px] shrink-0 font-sans" title={log.timestamp}>
                      {log.timestamp.includes(', ') ? log.timestamp.split(', ')[1] : log.timestamp}
                    </span>
                    <span className={`select-none text-[9px] uppercase px-1 bg-zinc-900 border border-zinc-800 rounded shrink-0 font-sans text-center w-[45px] ${
                      log.level === 'ERROR' ? 'border-rose-950 text-rose-500' :
                      log.level === 'WARN' ? 'border-amber-950 text-amber-500' :
                      'text-zinc-500'
                    }`}>
                      {log.level}
                    </span>
                    {log.taskId && (
                      <span className="text-primary/70 shrink-0 font-semibold max-w-[120px] truncate" title={log.taskId}>
                        [{log.taskId}]
                      </span>
                    )}
                    <span className={cn("break-words whitespace-pre-wrap flex-1 min-w-0", getLogLevelColor(log.level))}>
                      {log.message}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-2 text-zinc-500">
                <AlertCircle className="h-6 w-6 text-zinc-600" />
                Nenhum log encontrado para esta execução.
              </div>
            )}
          </div>
          
          <div className="p-4 border-t border-zinc-800 bg-zinc-900/30 flex justify-end gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSheetOpen(false)}
              className="rounded-lg border-zinc-800 hover:bg-zinc-900 hover:text-zinc-100 text-zinc-400 text-xs font-mono"
            >
              Fechar Console
            </Button>
            {selectedExec && (
              <a
                href={selectedExec.kestraUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  buttonVariants({ variant: "default", size: "sm" }),
                  "rounded-lg text-xs font-mono gap-1"
                )}
              >
                <ExternalLink className="h-3 w-3" />
                Kestra Completo
              </a>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
