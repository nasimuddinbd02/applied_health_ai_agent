// Login, current-user lookup, and patient self-signup.
import type { AuthUser, PatientSignup, TokenResponse } from "@/models/types";
import { BaseService } from "./baseService";

export class AuthService extends BaseService {
  login(email: string, password: string) {
    return this.http.post<TokenResponse>("/api/auth/login", { email, password });
  }
  me() {
    return this.http.get<AuthUser>("/api/auth/me");
  }
  signup(body: PatientSignup) {
    return this.http.post<TokenResponse>("/api/auth/register", body);
  }
}
