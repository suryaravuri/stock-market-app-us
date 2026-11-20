const ACCESS_TOKEN_KEY = "stock_access_token";

export const tokenService = {
  getToken(): string | null {
    return sessionStorage.getItem(ACCESS_TOKEN_KEY);
  },

  setToken(token: string): void {
    sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
  },

  clearToken(): void {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  },
};