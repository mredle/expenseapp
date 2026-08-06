import { Component, NgZone, OnDestroy, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { App as CapacitorApp } from '@capacitor/app';
import { AuthService } from './core/services/auth.service';

@Component({
  standalone: false,
  selector: 'app-root',
  templateUrl: 'app.component.html',
  styleUrls: ['app.component.scss'],
})
export class AppComponent implements OnInit, OnDestroy {
  private visibilityHandler = (): void => {
    if (document.visibilityState === 'visible') {
      this.zone.run(() => this.revalidateSession());
    }
  };

  constructor(
    private auth: AuthService,
    private router: Router,
    private zone: NgZone,
  ) {}

  ngOnInit(): void {
    // A suspended tab issues no HTTP requests, so an expired session would
    // otherwise go unnoticed: the page just sits there blank and the 401
    // interceptor never fires. Re-check whenever the app becomes visible.
    document.addEventListener('visibilitychange', this.visibilityHandler);
    CapacitorApp.addListener('appStateChange', ({ isActive }) => {
      if (isActive) this.zone.run(() => this.revalidateSession());
    }).catch(() => { /* not running under Capacitor */ });

    this.revalidateSession();
  }

  ngOnDestroy(): void {
    document.removeEventListener('visibilitychange', this.visibilityHandler);
  }

  /**
   * Validate (and if necessary renew) the session after the app regains focus.
   *
   * Expired sessions are cleared and the user is sent to the login page with a
   * returnUrl so they come back to the page they were on.
   */
  private revalidateSession(): void {
    if (!this.auth.token) return;

    if (this.auth.isExpired()) {
      this.redirectToLogin();
      return;
    }

    this.auth.refreshIfNeeded().subscribe(ok => {
      if (!ok) this.redirectToLogin();
    });
  }

  private redirectToLogin(): void {
    const returnUrl = this.router.url;
    this.auth.logout();
    if (returnUrl && !returnUrl.startsWith('/auth/')) {
      this.router.navigate(['/auth/login'], { queryParams: { returnUrl } });
    } else {
      this.router.navigate(['/auth/login']);
    }
  }
}
