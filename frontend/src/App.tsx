import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAdmin, RequireAuth } from "./auth/RequireAuth";
import { AppLayout } from "./layout/AppLayout";
import { Admin } from "./pages/Admin";
import { ChangePassword } from "./pages/ChangePassword";
import { Configuracion } from "./pages/Configuracion";
import { Login } from "./pages/Login";
import {
  Activos,
  Dashboard,
  Historial,
  Operaciones,
  Portfolio,
  Rendimiento,
} from "./pages/Secciones";
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
              <Route index element={<Dashboard />} />
              <Route path="portfolio" element={<Portfolio />} />
              <Route path="operaciones" element={<Operaciones />} />
              <Route path="activos" element={<Activos />} />
              <Route path="rendimiento" element={<Rendimiento />} />
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
