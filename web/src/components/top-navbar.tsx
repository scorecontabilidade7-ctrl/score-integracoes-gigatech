'use client'

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { LogOut } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { createClient } from "@/utils/supabase/client"

export function TopNavbar() {
  const pathname = usePathname()

  const handleLogout = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
    window.location.href = "/login"
  }

  const navItems = [
    { name: "GERAL", href: "/dashboard" },
    { name: "CONFIG. DE CLIENTES", href: "/dashboard/clientes" },
    { name: "LOGS", href: "/dashboard/logs" },
  ]

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-white shadow-sm h-20 flex items-center px-4 md:px-8 font-ui">
      <div className="flex items-center w-full justify-between">
        
        {/* Left: Logo */}
        <div className="flex items-center gap-4">
          <img 
            src="https://lunsyufvxkiivnrhpxpj.supabase.co/storage/v1/object/public/utils/logo_completa.png" 
            alt="Score Logo" 
            className="h-11 object-contain"
          />
        </div>

        {/* Center: Navigation Pills */}
        <div className="hidden md:flex items-center justify-center flex-1">
          <nav className="flex items-center bg-slate-50/80 border border-border/50 rounded-full p-1.5 shadow-inner">
            {navItems.map((item) => {
              const isActive = item.href === "/dashboard" 
                ? pathname === "/dashboard" 
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
