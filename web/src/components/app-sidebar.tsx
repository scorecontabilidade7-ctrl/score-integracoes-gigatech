'use client'

import * as React from "react"
import { Home, Users, LogOut, LayoutDashboard } from "lucide-react"
import { usePathname } from "next/navigation"
import Link from "next/link"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  useSidebar
} from "@/components/ui/sidebar"

// Mock for logout action. We can replace with server action later
import { createClient } from "@/utils/supabase/client"

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()
  const { state } = useSidebar()
  
  const handleLogout = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
    window.location.href = "/login"
  }

  return (
    <Sidebar collapsible="icon" {...props} className="border-r border-border/50 shadow-sm bg-white">
      <SidebarHeader className="h-16 flex justify-center border-b border-border/30 pb-2 mb-2">
        <div className="flex items-center justify-center h-full px-2">
           {state === "expanded" ? (
             <img 
               src="https://lunsyufvxkiivnrhpxpj.supabase.co/storage/v1/object/public/utils/logo_completa.png" 
               alt="Score Logo" 
               className="h-8 object-contain transition-all duration-200"
             />
           ) : (
             <img 
               src="https://lunsyufvxkiivnrhpxpj.supabase.co/storage/v1/object/public/utils/logo_simples.png" 
               alt="Score Logo" 
               className="h-8 w-8 object-contain transition-all duration-200"
             />
           )}
        </div>
      </SidebarHeader>
      
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-xs font-medium text-muted-foreground mb-2">
            Gestão
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton isActive={pathname === "/dashboard"} tooltip="Overview" render={<Link href="/dashboard" className="transition-colors hover:text-primary" />}>
                  <LayoutDashboard className="h-4 w-4" />
                  <span>Overview</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              
              <SidebarMenuItem>
                <SidebarMenuButton isActive={pathname.startsWith("/dashboard/clientes")} tooltip="Clientes" render={<Link href="/dashboard/clientes" className="transition-colors hover:text-primary" />}>
                  <Users className="h-4 w-4" />
                  <span>Clientes Cadastrados</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      
      <SidebarFooter className="border-t border-border/30 p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={handleLogout} className="text-muted-foreground hover:text-red-500 hover:bg-red-50 transition-colors" tooltip="Sair">
              <LogOut className="h-4 w-4" />
              <span>Sair do Sistema</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
