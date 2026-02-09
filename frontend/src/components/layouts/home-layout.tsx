import { ThemeToggle } from "@/components/theme/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NavigationMenu, NavigationMenuItem, NavigationMenuList } from "@/components/ui/navigation-menu";
import { ROUTES } from "@/config/routes";
import { useAuth } from "@/hooks/useAuth";
import { Link, Outlet } from "@tanstack/react-router";
import { LayoutDashboard, Menu } from "lucide-react";
import type { ReactNode } from "react";

interface HomeLayoutProps {
  children?: ReactNode;
}

export function HomeLayout({ children }: HomeLayoutProps) {
  const { isAuthenticated } = useAuth();

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="bg-background/95 supports-backdrop-filter:bg-background/60 border-b backdrop-blur">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <Link to={ROUTES.PUBLIC.HOME} className="flex items-center gap-2">
              <span className="text-lg font-bold">NexArena</span>
            </Link>
            {/* Desktop Navigation */}
            <NavigationMenu className="hidden md:flex">
              <NavigationMenuList>
                <NavigationMenuItem>
                  <Link to={ROUTES.PUBLIC.HOME}>
                    <Button variant="ghost">Home</Button>
                  </Link>
                </NavigationMenuItem>
                <NavigationMenuItem>
                  <Link to={ROUTES.PUBLIC.SOBRE}>
                    <Button variant="ghost">Sobre</Button>
                  </Link>
                </NavigationMenuItem>
                <NavigationMenuItem>
                  <Link to={ROUTES.PUBLIC.CONTATO}>
                    <Button variant="ghost">Contato</Button>
                  </Link>
                </NavigationMenuItem>
              </NavigationMenuList>
            </NavigationMenu>
          </div>
          <div className="flex items-center gap-2">
            {isAuthenticated && (
              <Link to={ROUTES.APP.DASHBOARD}>
                <Button variant="ghost" className="hidden gap-2 md:flex">
                  <LayoutDashboard className="h-4 w-4" />
                  Dashboard
                </Button>
              </Link>
            )}
            <ThemeToggle />
            {/* Mobile Menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild className="md:hidden">
                <Button variant="ghost" size="icon">
                  <Menu className="h-5 w-5" />
                  <span className="sr-only">Abrir menu</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                {isAuthenticated && (
                  <DropdownMenuItem asChild>
                    <Link to={ROUTES.APP.DASHBOARD} className="flex items-center gap-2">
                      <LayoutDashboard className="h-4 w-4" />
                      Dashboard
                    </Link>
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem asChild>
                  <Link to={ROUTES.PUBLIC.HOME}>Home</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to={ROUTES.PUBLIC.SOBRE}>Sobre</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to={ROUTES.PUBLIC.CONTATO}>Contato</Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">{children || <Outlet />}</main>

      {/* Footer */}
      <footer className="bg-background border-t">
        <div className="container mx-auto px-4 py-6">
          <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
            <div className="text-muted-foreground text-center text-sm md:text-left">
              <p>&copy; {new Date().getFullYear()} NexArena. Todos os direitos reservados.</p>
            </div>
            <nav className="flex gap-4">
              <Link to={ROUTES.PUBLIC.HOME}>
                <Button variant="ghost" size="sm" className="text-muted-foreground">
                  Home
                </Button>
              </Link>
              <Link to={ROUTES.PUBLIC.SOBRE}>
                <Button variant="ghost" size="sm" className="text-muted-foreground">
                  Sobre
                </Button>
              </Link>
              <Link to={ROUTES.PUBLIC.CONTATO}>
                <Button variant="ghost" size="sm" className="text-muted-foreground">
                  Contato
                </Button>
              </Link>
            </nav>
          </div>
        </div>
      </footer>
    </div>
  );
}
