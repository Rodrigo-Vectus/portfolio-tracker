import { Navigate, BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAdmin, RequireAuth } from "./auth/RequireAuth";
import { AppLayout } from "./layout/AppLayout";
import { Admin } from "./pages/Admin";
import { ChangePassword } from "./pages/ChangePassword";
import { Configuracion } from "./pages/Configuracion";
import { Login } from "./pages/Login";
import { Historial } from "./pages/Historial";
import { Cartera } from "./pages/Cartera";
import { Activos } from "./pages/Activos";
import { Cuentas } from "./pages/Cuentas";
import { Operaciones } from "./pages/Operaciones";

import { Estado } from "./pages/Estado";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route element={<RequireAuth />}>
            {/* Fuera del layout: mientras deba cambiar la clave no hay menú */}
            <Route path="/cambiar-contrasena" element={<ChangePassword />} />

            <Route element={<AppLayout />}>
              <Route index element={<Cartera />} />
              {/* Dashboard y Portfolio mostraban los mismos numeros con
                  distinto formato. Quedan como redireccion y no como 404:
                  las dos direcciones pueden estar guardadas en un favorito. */}
              <Route path="portfolio" element={<Navigate to="/" replace />} />
              <Route path="dashboard" element={<Navigate to="/" replace />} />
              <Route path="operaciones" element={<Operaciones />} />
              <Route path="activos" element={<Activos />} />
              <Route path="cuentas" element={<Cuentas />} />
              {/* Caja salio del producto: el sistema no es una billetera donde
                  se declara cuanta plata hay. Los depositos y retiros siguen
                  siendo tipos del libro y se cargan en Operaciones. */}
              <Route path="caja" element={<Navigate to="/operaciones" replace />} />
              <Route path="rendimiento" element={<Navigate to="/" replace />} />
              <Route path="historial" element={<Historial />} />
              <Route path="configuracion" element={<Configuracion />} />
              <Route path="estado" element={<Estado />} />

              <Route element={<RequireAdmin />}>
                <Route path="admin" element={<Admin />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<NoEncontrado />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

function NoEncontrado() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="max-w-sm">
        <h1 className="text-lg font-semibold">Esta página no existe.</h1>
        <a href="/" className="mt-2 inline-block text-sm text-brand hover:underline">
          Volver al inicio
        </a>
      </div>
    </main>
  );
}
