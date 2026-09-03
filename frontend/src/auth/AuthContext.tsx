/**
 * Estado de sesión de la aplicación.
 *
 * Al montar intenta renovar con la cookie de refresh: así una recarga de
 * página no obliga a volver a ingresar la contraseña, aunque el access token
 * no sobreviva al refresco del navegador.
 *
 * También programa la renovación silenciosa poco antes de que el token venza,
 * para que una sesión activa no se corte a mitad de una operación.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
  refreshSession,
  setAccessToken,
  setSessionLostHandler,
  type User,
} from "../lib/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthState | null>(null);

/** Margen antes del vencimiento para renovar sin que el usuario lo note. */
const RENEW_MARGIN_SECONDS = 60;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const renewTimer = useRef<number | null>(null);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    if (renewTimer.current) {
      clearTimeout(renewTimer.current);
      renewTimer.current = null;
    }
  }, []);

  const scheduleRenewal = useCallback(
    (expiresIn: number) => {
      if (renewTimer.current) clearTimeout(renewTimer.current);
      const delay = Math.max(expiresIn - RENEW_MARGIN_SECONDS, 30) * 1000;
      renewTimer.current = window.setTimeout(() => {
        void refreshSession().then((ok) => {
          if (ok) scheduleRenewal(expiresIn);
          else clearSession();
        });
      }, delay);
    },
    [clearSession],
  );

  useEffect(() => {
    setSessionLostHandler(clearSession);

    void (async () => {
      const renewed = await refreshSession();
      if (renewed) {
        const me = await fetchMe();
        if (me.ok) setUser(me.data);
      }
      setLoading(false);
    })();

    return () => {
      if (renewTimer.current) clearTimeout(renewTimer.current);
    };
  }, [clearSession]);

  const signIn = useCallback(
    async (email: string, password: string): Promise<string | null> => {
      const res = await apiLogin(email, password);
      if (!res.ok) return res.error;
      setAccessToken(res.data.access_token);
      setUser(res.data.user);
      scheduleRenewal(res.data.expires_in);
      return null;
    },
    [scheduleRenewal],
  );

  const signOut = useCallback(async () => {
    await apiLogout();
    clearSession();
  }, [clearSession]);

  const value = useMemo(
    () => ({ user, loading, signIn, signOut, setUser }),
    [user, loading, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
