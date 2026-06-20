'use client'

import * as React from "react"
import { Edit, Settings } from "lucide-react"

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
import { updateCliente } from "@/app/dashboard/clientes/actions"

interface EditClientDialogProps {
  cliente: {
    id: string;
    nome_loja: string;
    email_login_giga: string;
    senha_login_giga: string;
    ativo: boolean;
  }
}

export function EditClientDialog({ cliente }: EditClientDialogProps) {
  const [open, setOpen] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    
    const formData = new FormData(e.currentTarget)
    formData.append('id', cliente.id)

    const result = await updateCliente(formData)
    
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
          <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500 hover:text-slate-800" title="Editar Cliente">
            <Edit className="h-4 w-4" />
          </Button>
        }
      />
      <DialogContent className="sm:max-w-[425px] font-ui border-border/50 shadow-xl bg-white/95 backdrop-blur-md">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">Editar Cliente</DialogTitle>
          <DialogDescription>
            Altere as informações ou modifique o status da loja.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor={`edit-nome-${cliente.id}`} className="font-bold text-slate-700">Nome da Loja</Label>
            <Input
              id={`edit-nome-${cliente.id}`}
              name="nome"
              placeholder="Ex: LF Store"
              defaultValue={cliente.nome_loja}
              required
              className="bg-white"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor={`edit-email-${cliente.id}`} className="font-bold text-slate-700">E-mail (Giga Tech)</Label>
            <Input
              id={`edit-email-${cliente.id}`}
              name="email"
              type="email"
              placeholder="contato@loja.com"
              defaultValue={cliente.email_login_giga}
              required
              className="bg-white font-data text-sm"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor={`edit-senha-${cliente.id}`} className="font-bold text-slate-700">Senha (Giga Tech)</Label>
            <Input
              id={`edit-senha-${cliente.id}`}
              name="senha"
              type="text"
              placeholder="********"
              defaultValue={cliente.senha_login_giga}
              required
              className="bg-white font-data text-sm"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor={`edit-ativo-${cliente.id}`} className="font-bold text-slate-700">Status</Label>
            <select 
              id={`edit-ativo-${cliente.id}`}
              name="ativo" 
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-white px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              defaultValue={cliente.ativo ? "true" : "false"}
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
            {loading ? "Salvando..." : "Salvar Alterações"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
