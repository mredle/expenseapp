import { Injectable } from '@angular/core';
import { ActivatedRouteSnapshot, CanActivate, Router, RouterStateSnapshot } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Injectable({ providedIn: 'root' })
export class AuthGuard implements CanActivate {
  constructor(private auth: AuthService, private router: Router) {}

  canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): boolean {
    // isLoggedIn also checks expiry: a stale token must not activate the route,
    // otherwise the page renders empty and never prompts for re-authentication.
    if (this.auth.isLoggedIn) return true;

    this.auth.logout();
    // Preserve the attempted URL so the user returns here after signing in.
    this.router.navigate(['/auth/login'], { queryParams: { returnUrl: state.url } });
    return false;
  }
}
