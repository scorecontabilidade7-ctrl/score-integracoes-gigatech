'use client'

import * as React from "react"
import { Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createCliente } from "@/app/dashboard/clientes/actions"

export function NewClientDialog() {
  const [open, setOpen] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    
    const formData = new FormData(e.currentTarget)
    const result = await createCliente(formData)
    
    if (result.error) {
      setError(result.error)
      setLoading(false)
    } else {
      setOpen(false)
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger 
        render={
          <Button className="gap-2 font-bold tracking-wide shadow-md font-ui">
            <Plus className="h-4 w-4" /> Novo Cliente
          </Button>
        }
      />
      <DialogContent className="sm:max-w-[425px] font-ui border-border/50 shadow-xl bg-white/95 backdrop-blur-md">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">Cadastrar Novo Cliente</DialogTitle>
          <DialogDescription>
            Insira os dados da nova loja. O e-mail cadastrado será usado para controle de acesso.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="nome" className="font-bold text-slate-700">Nome da Loja</Label>
            <Input
              id="nome"
              name="nome"
              placeholder="Ex: LF Store"
              required
              className="bg-white"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="email" className="font-bold text-slate-700">E-mail (Giga Tech)</Label>
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="contato@loja.com"
              required
              className="bg-white font-data text-sm"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="senha" className="font-bold text-slate-700">Senha (Giga Tech)</Label>
            <Input
              id="senha"
              name="senha"
              type="password"
              placeholder="********"
              required
              className="bg-white font-data text-sm"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ativo" className="font-bold text-slate-700">Status</Label>
            <select 
              id="ativo"
              name="ativo" 
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-white px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              defaultValue="true"
            >
              <option value="true">Ativo</option>
              <option value="false">Inativo</option>
            </select>
          </div>
          
          {error && (
            <div className="text-sm text-red-500 font-medium bg-red-50 p-3 rounded-md">
              {error}
            </div>
          )}

          <Button type="submit" disabled={loading} className="w-full font-bold tracking-wide mt-2">
            {loading ? "Cadastrando..." : "Confirmar Cadastro"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
