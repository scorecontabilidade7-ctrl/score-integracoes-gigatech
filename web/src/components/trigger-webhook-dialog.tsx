'use client'

import * as React from "react"
import { format, differenceInDays } from "date-fns"
import { Calendar as CalendarIcon, Play } from "lucide-react"
import { DateRange } from "react-day-picker"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
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
      const url = process.env.NEXT_PUBLIC_KESTRA_WEBHOOK_URL
      if (!url || url === "COLOQUE_A_URL_DO_KESTRA_AQUI") {
        throw new Error("URL do Webhook não configurada no painel.")
      }

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          cliente_id: clienteId,
          data_inicial: format(date.from, "dd/MM/yyyy"),
          data_final: format(date.to, "dd/MM/yyyy")
        })
      })

      if (!response.ok) {
        throw new Error("Falha ao disparar automação no servidor Kestra.")
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

          {error && <div className="text-sm text-red-500 font-medium bg-red-50 p-2 rounded-lg">{error}</div>}
          {success && <div className="text-sm text-green-600 font-medium bg-green-50 p-2 rounded-lg">Fluxo disparado com sucesso! O Kestra já iniciou o processamento.</div>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} className="rounded-xl">Cancelar</Button>
          <Button type="button" onClick={handleExecute} disabled={loading || success} className="rounded-xl">
            {loading ? "Disparando..." : success ? "Enviado!" : "Confirmar Execução"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
