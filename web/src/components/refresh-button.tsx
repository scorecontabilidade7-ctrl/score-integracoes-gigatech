'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Clock } from 'lucide-react'

export default function RefreshButton() {
  const router = useRouter()
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      router.refresh()
      // Pequeno delay para a animação do ícone girar e dar feedback visual ao usuário
      await new Promise((resolve) => setTimeout(resolve, 800))
    } catch (e) {
      console.error(e)
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={handleRefresh}
      disabled={refreshing}
      className="rounded-xl border-black/5 hover:bg-black/[0.02]"
    >
      <Clock className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
      Atualizar
    </Button>
  )
}
