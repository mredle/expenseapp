import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, of, tap, catchError, map } from 'rxjs';
import { ApiService } from './api.service';
import { AuthResult } from '../models/models';

const TOKEN_KEY = 'ea_token';
const USER_KEY = 'ea_user';
const EXPIRY_KEY = 'ea_token_expires_at';

/** Refresh the token when it expires within this many milliseconds. */
const REFRESH_THRESHOLD_MS = 5 * 60 * 1000;

@Injectable({ providedIn: 'root' })
export class AuthService {
  private _token$ = new BehaviorSubject<string | null>(this.storedToken());
  private _userGuid$ = new BehaviorSubject<string | null>(localStorage.getItem(USER_KEY));

  token$ = this._token$.asObservable();
  isLoggedIn$ = new BehaviorSubject<boolean>(!!this.storedToken() && !this.isExpired());

  private refreshInFlight = false;

  constructor(private api: ApiService) {}

  get token(): string | null { return this._token$.value; }
  get userGuid(): string | null { return this._userGuid$.value; }

  /**
   * True only when a token is present *and* has not expired.
   *
   * The server issues short-lived tokens (1 h). Checking presence alone let an
   * expired session pass the route guard, which produced a blank page with no
   * re-authentication prompt.
   */
  get isLoggedIn(): boolean { return !!this.token && !this.isExpired(); }

  private storedToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  /** Token expiry in epoch milliseconds, or null when unknown. */
  get expiresAt(): number | null {
    const raw = localStorage.getItem(EXPIRY_KEY);
    if (!raw) return null;
    const ms = Date.parse(raw);
    return Number.isNaN(ms) ? null : ms;
  }

  /**
   * Whether the stored token is expired.
   *
   * When the server did not report an expiry (older API), we cannot know, so we
   * optimistically treat the token as valid and rely on the 401 interceptor.
   */
  isExpired(): boolean {
    const expiry = this.expiresAt;
    if (expiry === null) return false;
    return Date.now() >= expiry;
  }

  /** Whether the token is close enough to expiry that it should be renewed. */
  needsRefresh(): boolean {
    const expiry = this.expiresAt;
    if (expiry === null) return false;
    return Date.now() >= expiry - REFRESH_THRESHOLD_MS;
  }

  private storeAuth(token: string, userGuid: string, expiresAt?: string | null): void {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, userGuid);
    if (expiresAt) {
      localStorage.setItem(EXPIRY_KEY, expiresAt);
    } else {
      localStorage.removeItem(EXPIRY_KEY);
    }
    this._token$.next(token);
    this._userGuid$.next(userGuid);
    this.isLoggedIn$.next(true);
  }

  loginPassword(username: string, password: string): Observable<AuthResult> {
    return this.api.login(username, password).pipe(
      tap(res => this.storeAuth(res.token, res.user_guid, res.expires_at))
    );
  }

  loginWebAuthn(sessionId: string, credential: any): Observable<AuthResult> {
    return this.api.verifyWebAuthnAuth(sessionId, credential).pipe(
      tap(res => this.storeAuth(res.token, res.user_guid, res.expires_at))
    );
  }

  /**
   * Renew the token when it is nearing expiry.
   *
   * Resolves to true when the session is usable afterwards. A failed refresh
   * clears the session so callers can redirect to the login page.
   */
  refreshIfNeeded(): Observable<boolean> {
    if (!this.token) return of(false);
    if (this.isExpired()) {
      this.logout();
      return of(false);
    }
    if (!this.needsRefresh() || this.refreshInFlight) return of(true);

    this.refreshInFlight = true;
    return this.api.refreshToken().pipe(
      map(res => {
        this.refreshInFlight = false;
        localStorage.setItem(TOKEN_KEY, res.token);
        if (res.expires_at) localStorage.setItem(EXPIRY_KEY, res.expires_at);
        this._token$.next(res.token);
        this.isLoggedIn$.next(true);
        return true;
      }),
      catchError(() => {
        this.refreshInFlight = false;
        this.logout();
        return of(false);
      }),
    );
  }

  logout(): void {
    if (this.token && !this.isExpired()) {
      this.api.revokeToken().subscribe({ error: () => {} });
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(EXPIRY_KEY);
    this._token$.next(null);
    this._userGuid$.next(null);
    this.isLoggedIn$.next(false);
  }

  // EventUser GUID per event (stored in localStorage for the session)
  getEventUserGuid(eventGuid: string): string | null {
    return localStorage.getItem(`ea_eu_${eventGuid}`);
  }

  setEventUserGuid(eventGuid: string, euGuid: string): void {
    localStorage.setItem(`ea_eu_${eventGuid}`, euGuid);
  }
}
