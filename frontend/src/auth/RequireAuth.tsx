/**
 * Guardas de navegación.
 *
 * El control real de acceso vive en el backend: esto solo evita mostrar
 * pantallas que igual devolverían 401 o 403. Ocultar un botón no es seguridad.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

function Cargando() {
  return (
    <div className="flex min-h-screen items-center justify-center text-text-muted">
      Verificando sesión...
    </div>
  );
}

export function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <Cargando />;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;

  // Mientras deba cambiar la contraseña, no puede ir a ningún otro lado.
  if (user.must_change_password && location.pathname !== "/cambiar-contrasena") {
    return <Navigate to="/cambiar-contrasena" replace />;
  }

  return <Outlet />;
}

export function RequireAdmin() {
  const { user, loading } = useAuth();
  if (loading) return <Cargando />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "ADMIN") return <Navigate to="/" replace />;
  return <Outlet />;
}
