import { login } from './actions'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>
}) {
  const resolvedParams = await searchParams
  
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center">
          <img 
            src="https://lunsyufvxkiivnrhpxpj.supabase.co/storage/v1/object/public/utils/logo_completa.png" 
            alt="Score Logo" 
            className="h-16 object-contain mb-6"
          />
        </div>
        
        <Card className="border-0 shadow-lg shadow-black/5 rounded-2xl overflow-hidden">
          <CardHeader className="space-y-1 text-center pb-6">
            <CardTitle className="text-2xl font-bold tracking-tight text-foreground">
              Acesso Restrito
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              Insira suas credenciais para gerenciar o orquestrador
            </CardDescription>
          </CardHeader>
          <CardContent>
            {resolvedParams?.error && (
              <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-500 border border-red-100 text-center font-medium">
                {resolvedParams.error}
              </div>
            )}
            
            <form action={login} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="email">E-mail corporativo</Label>
                <Input 
                  id="email" 
                  name="email" 
                  type="email" 
                  autoComplete="email" 
                  required 
                  placeholder="seu@email.com"
                  className="rounded-xl h-11"
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">Senha</Label>
                </div>
                <Input 
                  id="password" 
                  name="password" 
                  type="password" 
                  autoComplete="current-password" 
                  required 
                  className="rounded-xl h-11"
                />
              </div>
              <Button type="submit" className="w-full rounded-xl h-11 text-base font-medium shadow-none hover:opacity-90 transition-opacity">
                Entrar
              </Button>
            </form>
          </CardContent>
        </Card>
        
        <p className="text-center text-sm text-muted-foreground">
          Score Multi-tenant Orchestrator v2.0
        </p>
      </div>
    </div>
  )
}
