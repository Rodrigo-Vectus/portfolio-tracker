import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Button, ErrorNote, Field } from "../components/ui";

export function Login() {
  const { user, loading, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    const from = (location.state as { from?: Location })?.from?.pathname ?? "/";
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const message = await signIn(email, password);
    setSubmitting(false);
    if (message) setError(message);
    else navigate("/", { replace: true });
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-3">
          <img
            src="/logo.png"
            alt=""
            className="h-12 w-12 shrink-0 rounded-lg object-cover"
          />
          <div className="leading-none">
            <p className="wordmark text-lg leading-tight">Portfolio</p>
            <p className="wordmark text-lg leading-tight text-brand">Tracker</p>
          </div>
        </div>

        <p className="eyebrow mb-2">Acceso</p>
        <h1 className="display text-xl">Ingresá para ver tu cartera</h1>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <Field
            label="Email"
            type="email"
            autoComplete="username"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Field
            label="Contraseña"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && <ErrorNote>{error}</ErrorNote>}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Ingresando..." : "Ingresar"}
          </Button>
        </form>

        <p className="mt-8 text-sm text-text-faint">
          Las cuentas las crea un administrador. No hay registro abierto.
        </p>
      </div>
    </main>
  );
}
