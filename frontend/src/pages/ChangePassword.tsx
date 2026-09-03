import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { changePassword } from "../lib/api";
import { Button, ErrorNote, Field } from "../components/ui";

export function ChangePassword() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const obligatorio = user?.must_change_password ?? false;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (next !== repeat) {
      setError("Las dos contraseñas nuevas no coinciden.");
      return;
    }
    setSubmitting(true);
    setError(null);
    const res = await changePassword(current, next);
    setSubmitting(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setUser(res.data);
    navigate("/", { replace: true });
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="text-xl font-semibold tracking-tight">
          {obligatorio ? "Elegí tu contraseña" : "Cambiar contraseña"}
        </h1>
        <p className="mt-1 max-w-prose text-text-muted">
          {obligatorio
            ? "Tu cuenta se creó con una contraseña temporal que está escrita en el archivo de configuración del servidor. Cambiala antes de seguir."
            : "Al cambiarla se cierran todas tus sesiones abiertas."}
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <Field
            label="Contraseña actual"
            type="password"
            autoComplete="current-password"
            required
            autoFocus
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
          <Field
            label="Contraseña nueva"
            type="password"
            autoComplete="new-password"
            required
            hint="Al menos 10 caracteres, con letras y números."
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
          <Field
            label="Repetir la nueva"
            type="password"
            autoComplete="new-password"
            required
            value={repeat}
            onChange={(e) => setRepeat(e.target.value)}
          />

          {error && <ErrorNote>{error}</ErrorNote>}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Guardando..." : "Guardar contraseña"}
          </Button>
        </form>
      </div>
    </main>
  );
}
