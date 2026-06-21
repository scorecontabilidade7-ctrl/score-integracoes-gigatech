'use client'

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { LogOut, ChevronDown, ArrowLeftRight } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { createClient } from "@/utils/supabase/client"
import { SYSTEMS } from "@/utils/systems"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface TopNavbarProps {
  systemId: string
}

export function TopNavbar({ systemId }: TopNavbarProps) {
  const pathname = usePathname()
  const currentSystem = SYSTEMS[systemId]

  const handleLogout = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
    window.location.href = "/login"
  }

  const navItems = [
    { name: "GERAL", href: `/dashboard/${systemId}` },
    { name: "CONFIG. DE CLIENTES", href: `/dashboard/${systemId}/clientes` },
    { name: "LOGS", href: `/dashboard/${systemId}/logs` },
  ]

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-white shadow-sm h-20 flex items-center px-4 md:px-8 font-ui">
      <div className="flex items-center w-full justify-between">
        
        {/* Left: Logo & Dropdown Selector */}
        <div className="flex items-center gap-3">
          <Link href="/dashboard">
            <img 
              src="https://lunsyufvxkiivnrhpxpj.supabase.co/storage/v1/object/public/utils/logo_completa.png" 
              alt="Score Logo" 
              className="h-11 object-contain cursor-pointer"
            />
          </Link>

          <div className="h-6 w-[1px] bg-slate-200 mx-2 hidden sm:block" />

          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button 
                  variant="outline" 
                  className="h-10 rounded-full border-slate-200 bg-slate-50 hover:bg-slate-100/80 px-4 font-ui text-xs font-bold gap-2 text-slate-700 shadow-sm"
                >
                  <ArrowLeftRight className="h-3.5 w-3.5 text-slate-400" />
                  <span>{currentSystem?.name || "Selecionar Sistema"}</span>
                  <ChevronDown className="h-3 w-3 text-slate-400" />
                </Button>
              }
            />
            <DropdownMenuContent align="start" className="w-[200px] font-ui bg-white rounded-2xl shadow-xl border border-slate-100 p-1.5 mt-2">
              {Object.values(SYSTEMS).map((sys) => (
                <DropdownMenuItem
                  key={sys.id}
                  render={
                    <Link 
                      href={`/dashboard/${sys.id}`}
                      className={cn(
                        "flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-all",
                        sys.id === systemId 
                          ? "bg-slate-100 text-slate-900 font-bold" 
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                      )}
                    >
                      <div className={cn(
                        "h-2 w-2 rounded-full",
                        sys.id === systemId ? "bg-emerald-500 animate-pulse" : "bg-slate-300"
                      )} />
                      {sys.name}
                    </Link>
                  }
                />
              ))}
              <div className="h-[1px] bg-slate-100 my-1.5" />
              <DropdownMenuItem
                render={
                  <Link 
                    href="/dashboard"
                    className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-slate-500 hover:bg-red-50 hover:text-red-600 cursor-pointer transition-all"
                  >
                    <ArrowLeftRight className="h-3.5 w-3.5" />
                    Voltar ao Portal
                  </Link>
                }
              />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Center: Navigation Pills */}
        <div className="hidden md:flex items-center justify-center flex-1">
          <nav className="flex items-center bg-slate-50/80 border border-border/50 rounded-full p-1.5 shadow-inner">
            {navItems.map((item) => {
              const isActive = item.href === `/dashboard/${systemId}`
                ? pathname === `/dashboard/${systemId}`
                : pathname.startsWith(item.href)
                
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "px-6 py-2 rounded-full text-xs font-bold tracking-wider transition-all",
                    isActive 
                      ? "bg-slate-800 text-white shadow-md" 
                      : "text-slate-500 hover:text-slate-800 hover:bg-slate-200/50"
                  )}
                >
                  {item.name}
                </Link>
              )
            })}
          </nav>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-3">
          <Button 
            variant="outline" 
            onClick={handleLogout}
            className="h-10 rounded-full border-red-200 text-red-500 hover:bg-red-50 hover:text-red-600 gap-2 px-4 text-xs font-bold tracking-wider"
          >
            <LogOut className="h-4 w-4" />
            SAIR
          </Button>
        </div>

      </div>
    </header>
  )
}
