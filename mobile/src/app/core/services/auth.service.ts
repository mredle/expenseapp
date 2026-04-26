import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { ApiService } from './api.service';
import { AuthResult } from '../models/models';

const TOKEN_KEY = 'ea_token';
const USER_KEY = 'ea_user';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private _token$ = new BehaviorSubject<string | null>(this.storedToken());
  private _userGuid$ = new BehaviorSubject<string | null>(localStorage.getItem(USER_KEY));

  token$ = this._token$.asObservable();
  isLoggedIn$ = new BehaviorSubject<boolean>(!!this.storedToken());

  constructor(private api: ApiService) {}

  get token(): string | null { return this._token$.value; }
  get userGuid(): string | null { return this._userGuid$.value; }
  get isLoggedIn(): boolean { return !!this.token; }

  private storedToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  private storeAuth(token: string, userGuid: string): void {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, userGuid);
    this._token$.next(token);
    this._userGuid$.next(userGuid);
    this.isLoggedIn$.next(true);
  }

  loginPassword(username: string, password: string): Observable<AuthResult> {
    return this.api.login(username, password).pipe(
      tap(res => this.storeAuth(res.token, res.user_guid))
    );
  }

  loginWebAuthn(sessionId: string, credential: any): Observable<AuthResult> {
    return this.api.verifyWebAuthnAuth(sessionId, credential).pipe(
      tap(res => this.storeAuth(res.token, res.user_guid))
    );
  }

  logout(): void {
    if (this.token) {
      this.api.revokeToken().subscribe({ error: () => {} });
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
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
