/**
 * Barra lateral.
 *
 * Sigue la estructura de la referencia: marca arriba, secciones agrupadas con
 * etiqueta, y cada ítem con ícono, título y una línea que explica qué hay
 * adentro.
 *
 * El subtítulo no es decoración. En una aplicación financiera "Caja" y
 * "Portfolio" no se distinguen solos, y la línea de abajo evita entrar a
 * adivinar.
 */

import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  IconAdmin,
  IconConfiguracion,
  IconEstado,
  IconOperaciones,
  IconPortfolio,
  IconSalir,
} from "../components/icons";

interface Item {
  to: string;
  label: string;
  detalle: string;
  icono: (p: { className?: string }) => JSX.Element;
  adminOnly?: boolean;
}

interface Seccion {
  titulo: string;
  items: Item[];
}

const SECCIONES: Seccion[] = [
  {
    titulo: "Cartera",
    items: [
      {
        to: "/",
        label: "Cartera",
        detalle: "Posiciones, resultado y evolución",
        icono: IconPortfolio,
      },
      {
        to: "/operaciones",
        label: "Operaciones",
        detalle: "Compras, ventas y movimientos",
        icono: IconOperaciones,
      },
    ],
  },
  {
    titulo: "Sistema",
    items: [
      {
        to: "/configuracion",
        label: "Configuración",
        detalle: "Tu cuenta y los valores por defecto",
        icono: IconConfiguracion,
      },
      {
        to: "/estado",
        label: "Estado",
        detalle: "Servicios y diagnóstico",
        icono: IconEstado,
      },
      {
        to: "/admin",
        label: "Administración",
        detalle: "Usuarios de la plataforma",
        icono: IconAdmin,
        adminOnly: true,
      },
    ],
  },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, signOut } = useAuth();

  return (
    <div className="flex h-full flex-col border-r border-ink-600 bg-ink-900">
      {/* Marca */}
      <div className="flex items-center gap-3 border-b border-ink-600 px-4 py-4">
        <img
          src="/logo.png"
          alt=""
          className="h-10 w-10 shrink-0 rounded-lg object-cover"
        />
        <div className="min-w-0 leading-none">
          <p className="display text-sm leading-tight">Portfolio</p>
          <p className="display text-sm leading-tight text-brand">Tracker</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {SECCIONES.map((seccion) => {
          const visibles = seccion.items.filter(
            (i) => !i.adminOnly || user?.role === "ADMIN",
          );
          if (visibles.length === 0) return null;

          return (
            <div key={seccion.titulo} className="mb-6">
              <p className="eyebrow mb-2 px-2">{seccion.titulo}</p>
              <ul className="space-y-0.5">
                {visibles.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.to === "/"}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        `flex items-start gap-3 rounded-lg px-2.5 py-2 transition-colors ${
                          isActive
                            ? "bg-brand-soft text-text"
                            : "text-text-muted hover:bg-ink-800 hover:text-text"
                        }`
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <span
                            className={`mt-0.5 flex h-7 w-7 shrink-0 items-center
                                        justify-center rounded-md border ${
                                          isActive
                                            ? "border-brand/40 bg-brand/15 text-brand"
                                            : "border-ink-600 bg-ink-800 text-text-faint"
                                        }`}
                          >
                            <item.icono />
                          </span>
                          <span className="min-w-0">
                            <span
                              className={`block text-sm font-medium leading-tight ${
                                isActive ? "text-brand" : ""
                              }`}
                            >
                              {item.label}
                            </span>
                            <span className="mt-0.5 block truncate text-micro text-text-faint">
                              {item.detalle}
                            </span>
                          </span>
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </nav>

      <div className="border-t border-ink-600 px-4 py-4">
        <p className="truncate text-sm font-medium">{user?.name}</p>
        <p className="truncate text-micro text-text-faint">{user?.email}</p>
        {user?.role === "ADMIN" && (
          <p className="mt-2">
            <span
              className="code inline-flex items-center rounded-full border
                         border-brand/40 bg-brand-soft px-2 py-0.5 text-micro
                         uppercase tracking-wider text-brand"
            >
              Administrador
            </span>
          </p>
        )}
        <button
          onClick={() => void signOut()}
          className="mt-3 flex items-center gap-2 text-sm text-text-muted
                     transition-colors hover:text-brand"
        >
          <IconSalir />
          Cerrar sesión
        </button>
      </div>
    </div>
  );
}
