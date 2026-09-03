import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../components/ui";

interface Item {
  to: string;
  label: string;
  adminOnly?: boolean;
}

const ITEMS: Item[] = [
  { to: "/", label: "Dashboard" },
  { to: "/portfolio", label: "Portfolio" },
  { to: "/operaciones", label: "Operaciones" },
  { to: "/activos", label: "Activos" },
  { to: "/rendimiento", label: "Rendimiento" },
  { to: "/historial", label: "Historial" },
  { to: "/configuracion", label: "Configuración" },
  { to: "/estado", label: "Estado del sistema" },
  { to: "/admin", label: "Administración", adminOnly: true },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, signOut } = useAuth();
  const visible = ITEMS.filter((i) => !i.adminOnly || user?.role === "ADMIN");

  return (
    <div className="flex h-full flex-col border-r border-ink-600 bg-ink-800">
      <div className="border-b border-ink-600 px-5 py-5">
        <span className="font-semibold tracking-tight">Portfolio Tracker</span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <ul className="space-y-0.5">
          {visible.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `block rounded px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? "bg-ink-700 font-medium text-text"
                      : "text-text-muted hover:bg-ink-700/60 hover:text-text"
                  }`
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="border-t border-ink-600 px-5 py-4">
        <p className="truncate text-sm font-medium">{user?.name}</p>
        <p className="truncate text-sm text-text-faint">{user?.email}</p>
        {user?.role === "ADMIN" && (
          <p className="mt-1 text-micro text-brand">Administrador</p>
        )}
        <Button variant="ghost" className="mt-3 -ml-4" onClick={() => void signOut()}>
          Cerrar sesión
        </Button>
      </div>
    </div>
  );
}
