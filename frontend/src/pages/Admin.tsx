import { useEffect, useState } from "react";
import { fetchUsers, type User } from "../lib/api";
import { EmptyState, ErrorNote, PageHeading } from "../components/ui";

export function Admin() {
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchUsers().then((r) => (r.ok ? setUsers(r.data) : setError(r.error)));
  }, []);

  return (
    <>
      <PageHeading
        title="Administración"
        subtitle="Gestión de la plataforma. No da acceso a las carteras de otras personas."
      />

      {error && <ErrorNote>{error}</ErrorNote>}

      {users && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ink-600 text-left text-text-muted">
              <th className="pb-2 font-medium">Nombre</th>
              <th className="pb-2 font-medium">Email</th>
              <th className="pb-2 font-medium">Rol</th>
              <th className="pb-2 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-ink-600/60">
                <td className="py-2.5">{u.name}</td>
                <td className="py-2.5 text-text-muted">{u.email}</td>
                <td className="py-2.5">{u.role === "ADMIN" ? "Administrador" : "Usuario"}</td>
                <td className={`py-2.5 ${u.is_active ? "text-gain" : "text-loss"}`}>
                  {u.is_active ? "Activo" : "Desactivado"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="mt-10">
        <EmptyState
          title="La administración completa llega en la fase 7."
          detail="Crear y desactivar usuarios, gestionar permisos y consultar la bitácora de auditoría. La bitácora ya se está escribiendo: cada ingreso, cambio de contraseña y renovación de sesión queda registrado."
        />
      </div>
    </>
  );
}
