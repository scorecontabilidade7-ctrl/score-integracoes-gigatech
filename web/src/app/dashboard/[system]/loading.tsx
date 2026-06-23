import { Loader2 } from "lucide-react"

export default function Loading() {
  return (
    <div className="flex h-[50vh] w-full items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-slate-500 animate-in fade-in duration-500">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        <p className="text-sm font-medium tracking-wide">Carregando dados...</p>
      </div>
    </div>
  )
}
