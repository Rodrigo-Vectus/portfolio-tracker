import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  const [openOnMobile, setOpenOnMobile] = useState(false);

  return (
    <div className="flex min-h-screen">
      {/* Barra lateral fija en escritorio */}
      <aside className="hidden w-60 shrink-0 lg:block">
        <div className="fixed inset-y-0 w-60">
          <Sidebar />
        </div>
      </aside>

      {/* En móvil se despliega sobre el contenido */}
      {openOnMobile && (
        <div className="fixed inset-0 z-20 lg:hidden">
          <button
            className="absolute inset-0 bg-ink-900/80"
            aria-label="Cerrar menú"
            onClick={() => setOpenOnMobile(false)}
          />
          <div className="absolute inset-y-0 left-0 w-60">
            <Sidebar onNavigate={() => setOpenOnMobile(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-ink-600 px-4 py-3 lg:hidden">
          <button
            className="text-sm text-text-muted"
            onClick={() => setOpenOnMobile(true)}
          >
            Menú
          </button>
        </div>
        <main className="flex-1 px-6 py-10 lg:px-10">
          <div className="mx-auto max-w-4xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
