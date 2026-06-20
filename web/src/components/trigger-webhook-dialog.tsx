'use client'

import * as React from "react"
import { format, differenceInDays } from "date-fns"
import { Calendar as CalendarIcon, Play } from "lucide-react"
import { DateRange } from "react-day-picker"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { triggerKestraFlow } from "@/app/dashboard/clientes/actions"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Label } from "@/components/ui/label"

interface TriggerWebhookDialogProps {
  clienteId: string
  clienteNome: string
}

export function TriggerWebhookDialog({ clienteId, clienteNome }: TriggerWebhookDialogProps) {
  const [open, setOpen] = React.useState(false)
  const [date, setDate] = React.useState<DateRange | undefined>()
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [success, setSuccess] = React.useState(false)

  const daysDifference = React.useMemo(() => {
    if (!date?.from || !date?.to) return null
    return differenceInDays(date.to, date.from)
  }, [date])

  const isPeriodValid = React.useMemo(() => {
    if (daysDifference === null) return false
    return daysDifference >= 0 && daysDifference <= 31
  }, [daysDifference])

  const handleExecute = async () => {
    if (!date?.from || !date?.to) {
      setError("Selecione um período de datas.")
      return
    }

    const days = differenceInDays(date.to, date.from)
    if (days > 31) {
      setError("O período não pode ser superior a 31 dias.")
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(false)

    try {
      const res = await triggerKestraFlow(
        clienteId,
        format(date.from, "dd/MM/yyyy"),
        format(date.to, "dd/MM/yyyy")
      )

      if (res?.error) {
        throw new Error(res.error)
      }

      setSuccess(true)
      setTimeout(() => {
        setOpen(false)
        setSuccess(false)
        setDate(undefined)
      }, 3000)

    } catch (err: any) {
      setError(err.message || "Erro desconhecido ao acionar webhook.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={
        <Button variant="outline" size="sm" className="h-8 gap-1.5 rounded-xl text-primary border-primary/20 bg-primary/5 hover:bg-primary/10">
          <Play className="h-3.5 w-3.5" />
          Executar Fluxo
        </Button>
      } />
      <DialogContent className="sm:max-w-[425px] rounded-2xl border-0 shadow-xl">
        <DialogHeader>
          <DialogTitle>Executar Retroativo</DialogTitle>
          <DialogDescription>
            Defina o período para extrair e processar os dados da loja <strong>{clienteNome}</strong>.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="space-y-2">
            <Label>Período (Máx 31 dias)</Label>
            <Popover>
              <PopoverTrigger render={
                <Button
                  id="date"
                  variant={"outline"}
                  className={cn(
                    "w-full justify-start text-left font-normal h-11 rounded-xl",
                    !date && "text-muted-foreground"
                  )}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {date?.from ? (
                    date.to ? (
                      <>
                        {format(date.from, "dd/MM/yyyy")} -{" "}
                        {format(date.to, "dd/MM/yyyy")}
                      </>
                    ) : (
                      format(date.from, "dd/MM/yyyy")
                    )
                  ) : (
                    <span>Selecione uma data</span>
                  )}
                </Button>
              } />
              <PopoverContent className="w-auto p-0 rounded-2xl" align="start">
                <Calendar
                  mode="range"
                  defaultMonth={date?.from}
                  selected={date}
                  onSelect={(range) => {
                     setError(null)
                     setDate(range)
                  }}
                  numberOfMonths={1}
                />
              </PopoverContent>
            </Popover>
          </div>

          {daysDifference !== null && daysDifference > 31 && (
            <div className="text-xs text-amber-600 bg-amber-50 p-2 rounded-lg border border-amber-200">
              ⚠️ O período selecionado ({daysDifference} dias) excede o limite de 31 dias.
            </div>
          )}

          {error && <div className="text-sm text-red-500 font-medium bg-red-50 p-2 rounded-lg">{error}</div>}
          {success && <div className="text-sm text-green-600 font-medium bg-green-50 p-2 rounded-lg">Fluxo disparado com sucesso! O Kestra já iniciou o processamento.</div>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} className="rounded-xl">Cancelar</Button>
          <Button type="button" onClick={handleExecute} disabled={loading || success || !isPeriodValid} className="rounded-xl">
            {loading ? "Disparando..." : success ? "Enviado!" : "Confirmar Execução"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
