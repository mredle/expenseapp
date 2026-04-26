import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  standalone: false,
  selector: 'app-admin',
  template: `
    <ion-header>
      <ion-toolbar color="primary">
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/events"></ion-back-button></ion-buttons>
        <ion-title>Admin</ion-title>
      </ion-toolbar>
    </ion-header>
    <ion-content>
      <ion-list>
        <ion-item button (click)="go('logs')">
          <ion-icon slot="start" name="list"></ion-icon>
          <ion-label>Logs</ion-label>
        </ion-item>
        <ion-item button (click)="go('tasks')">
          <ion-icon slot="start" name="timer"></ion-icon>
          <ion-label>Tasks</ion-label>
        </ion-item>
        <ion-item button (click)="go('statistics')">
          <ion-icon slot="start" name="bar-chart"></ion-icon>
          <ion-label>Statistics</ion-label>
        </ion-item>
      </ion-list>
    </ion-content>
  `,
})
export class AdminPage {
  constructor(private router: Router, private auth: AuthService) {}
  go(sub: string): void { this.router.navigate(['/admin', sub]); }
}
