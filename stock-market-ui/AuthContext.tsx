import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  getCurrentUser,
  login as loginRequest,
} from "../services/authService";
import { tokenService } from "../services/tokenService";

import type {
  AuthUser,
  LoginRequest,
} from "../types/auth";


interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;

  login: (request: LoginRequest) => Promise<void>;
  logout: () => void;
}


const AuthContext = createContext<AuthContextValue | undefined>(
  undefined
);


export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);


  useEffect(() => {
    const restoreSession = async () => {
      const token = tokenService.getToken();

      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const currentUser = await getCurrentUser();
        setUser(currentUser);
      } catch {
        tokenService.clearToken();
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    void restoreSession();
  }, []);


  const login = async (
    request: LoginRequest
  ): Promise<void> => {
    const response = await loginRequest(request);

    tokenService.setToken(response.access_token);

    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      tokenService.clearToken();
      setUser(null);
      throw error;
    }
  };


  const logout = (): void => {
    tokenService.clearToken();
    setUser(null);
  };


  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: user !== null,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}


export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider"
    );
  }

  return context;
}