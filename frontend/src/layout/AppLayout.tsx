import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  const [openOnMobile, setOpenOnMobile] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Barra lateral fija en escritorio. Más ancha que antes porque cada
          ítem ahora lleva una línea de descripción debajo. */}
      <aside className="hidden w-72 shrink-0 lg:block">
        <div className="fixed inset-y-0 w-72">
          <Sidebar />
        </div>
      </aside>

      {/* En móvil se despliega sobre el contenido */}
      {openOnMobile && (
        <div className="fixed inset-0 z-20 lg:hidden">
          <button
            className="absolute inset-0 bg-ink-950/85 backdrop-blur-sm"
            aria-label="Cerrar menú"
            onClick={() => setOpenOnMobile(false)}
          />
          <div className="absolute inset-y-0 left-0 w-72">
            <Sidebar onNavigate={() => setOpenOnMobile(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-3 border-b border-ink-600 px-4 py-3 lg:hidden">
          <button
            className="flex items-center gap-2 text-sm text-text-muted"
            onClick={() => setOpenOnMobile(true)}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.8}
              strokeLinecap="round"
              className="h-5 w-5"
              aria-hidden="true"
            >
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
            Menú
          </button>
        </div>
        <main className="flex-1 px-6 py-10 lg:px-12">
          <div className="mx-auto max-w-5xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
