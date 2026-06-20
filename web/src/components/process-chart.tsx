'use client'

import { useState, useEffect } from 'react'
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Cell 
} from 'recharts'
import { KestraExecution } from '@/utils/kestra'
import { fetchKestraExecutionsAction } from '@/app/dashboard/logs/actions'
import { Card, CardContent } from '@/components/ui/card'
import { AlertCircle, Activity } from 'lucide-react'

interface ProcessChartProps {
  executions: KestraExecution[]
}

export default function ProcessChart({ executions }: ProcessChartProps) {
  const [currentExecutions, setCurrentExecutions] = useState<KestraExecution[]>(executions)

  // Sincroniza o estado se as props mudarem (ex: clique no botão de atualizar no pai)
  useEffect(() => {
    setCurrentExecutions(executions)
  }, [executions])

  // Efeito 1: Polling da API a cada 4 segundos se houver alguma execução rodando
  useEffect(() => {
    const hasRunning = currentExecutions.some(e => e.status === 'Em Execução')
    if (!hasRunning) return

    const poll = async () => {
      try {
        const res = await fetchKestraExecutionsAction()
        if (res.success && res.executions) {
          setCurrentExecutions(res.executions)
        }
      } catch (err) {
        console.error("Erro no polling de execuções no gráfico:", err)
      }
    }

    const intervalId = setInterval(poll, 4000)
    return () => clearInterval(intervalId)
  }, [currentExecutions])

  // Efeito 2: Incrementa em tempo real a duração da barra rodando a cada 1 segundo
  useEffect(() => {
    const hasRunning = currentExecutions.some(e => e.status === 'Em Execução')
    if (!hasRunning) return

    const increment = () => {
      setCurrentExecutions(prev => 
        prev.map(e => {
          if (e.status === 'Em Execução') {
            const nextDuration = e.durationSeconds + 1
            const mins = Math.floor(nextDuration / 60)
            const secs = nextDuration % 60
            const tempoStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`
            
            return {
              ...e,
              durationSeconds: nextDuration,
              tempo: tempoStr
            }
          }
          return e
        })
      )
    }

    const intervalId = setInterval(increment, 1000)
    return () => clearInterval(intervalId)
  }, [currentExecutions])

  if (!currentExecutions || currentExecutions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-sm text-muted-foreground min-h-[300px] gap-2">
        <Activity className="h-8 w-8 text-muted-foreground/30 animate-pulse" />
        <span>Nenhum dado de execução encontrado no Kestra.</span>
      </div>
    )
  }

  // Pegar as últimas 15 execuções e ordenar cronologicamente (da mais antiga para a mais recente)
  const chartData = [...currentExecutions]
    .slice(0, 15)
    .reverse()
    .map(e => {
      // Extrair "DD/MM HH:MM" da data formatada "DD/MM/YYYY HH:MM:SS"
      const dateParts = e.data.split(' ')
      let name = 'N/A'
      if (dateParts.length >= 2) {
        const dateOnly = dateParts[0].substring(0, 5) // DD/MM
        const timeOnly = dateParts[1].substring(0, 5) // HH:MM
        name = `${dateOnly} ${timeOnly}`
      }
      
      return {
        name,
        duration: e.durationSeconds,
        tempoStr: e.tempo,
        status: e.status,
        cliente: e.cliente,
        id: e.id,
      }
    })

  const getBarColor = (status: string) => {
    switch (status) {
      case 'Sucesso':
        return '#10b981' // emerald-500
      case 'Em Execução':
        return '#3b82f6' // blue-500
      case 'Pausado':
        return '#f59e0b' // amber-500
      default:
        return '#f43f5e' // rose-500
    }
  }

  // Formatador de Y Axis (ex: 60 -> 1m, 120 -> 2m)
  const formatYAxis = (seconds: number) => {
    if (seconds === 0) return '0s'
    if (seconds < 60) return `${seconds}s`
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`
  }

  return (
    <div className="w-full h-[320px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          style={{ outline: 'none' }}
          margin={{
            top: 10,
            right: 10,
            left: -15,
            bottom: 0,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          <XAxis 
            dataKey="name" 
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'var(--font-mono, monospace)' }}
          />
          <YAxis 
            tickLine={false}
            axisLine={false}
            tickFormatter={formatYAxis}
            tick={{ fill: '#64748b', fontSize: 10 }}
          />
          <Tooltip
            cursor={{ fill: 'transparent' }}
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload
                return (
                  <div className="bg-zinc-950 text-zinc-100 p-3 rounded-xl border border-zinc-800 shadow-xl font-mono text-[10px] space-y-1.5 min-w-[200px]">
                    <div className="font-semibold text-zinc-400 border-b border-zinc-800 pb-1 flex justify-between items-center">
                      <span>Execução: {data.id}</span>
                      <span style={{ color: getBarColor(data.status) }} className="text-[9px] uppercase font-bold">
                        {data.status}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500">Cliente:</span>{' '}
                      <span className="text-zinc-300 font-sans">{data.cliente}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500">Início:</span>{' '}
                      <span className="text-zinc-300">{data.name}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500">Duração:</span>{' '}
                      <span className="text-zinc-200 font-bold">{data.tempoStr}</span>
                    </div>
                  </div>
                )
              }
              return null
            }}
          />
          <Bar dataKey="duration" radius={[4, 4, 0, 0]} maxBarSize={40}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getBarColor(entry.status)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
