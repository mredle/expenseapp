import { Injectable, OnDestroy } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { ToastController } from '@ionic/angular';
import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { Notification } from '../models/models';

const POLL_INTERVAL_MS = 30_000;

@Injectable({ providedIn: 'root' })
export class NotificationService implements OnDestroy {
  /** Unread message count badge */
  unreadCount$ = new BehaviorSubject<number>(0);

  private lastTimestamp = 0;
  private timerId: ReturnType<typeof setInterval> | null = null;

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private toast: ToastController,
  ) {
    // Start polling whenever the user is logged in
    this.auth.isLoggedIn$.subscribe(loggedIn => {
      if (loggedIn) { this.start(); } else { this.stop(); this.unreadCount$.next(0); }
    });
  }

  private start(): void {
    if (this.timerId !== null) { return; }
    // poll immediately, then on interval
    this.poll();
    this.timerId = setInterval(() => this.poll(), POLL_INTERVAL_MS);
  }

  private stop(): void {
    if (this.timerId !== null) { clearInterval(this.timerId); this.timerId = null; }
    this.lastTimestamp = 0;
  }

  private poll(): void {
    if (!this.auth.isLoggedIn) { return; }
    this.api.getNotifications(this.lastTimestamp).subscribe({
      next: res => {
        if (!res.items?.length) { return; }
        this.lastTimestamp = Math.max(...res.items.map(n => n.timestamp));
        this.processNotifications(res.items);
      },
      error: () => { /* silent – no auth/connectivity noise */ },
    });
  }

  private processNotifications(items: Notification[]): void {
    for (const n of items) {
      if (n.name === 'unread_message_count') {
        this.unreadCount$.next(n.data as number);
      } else if (n.name === 'task_progress') {
        const prog: { description: string; progress: number } = n.data;
        if (prog.progress >= 100) {
          this.toast.create({
            message: `Task complete: ${prog.description}`,
            duration: 3000,
            color: 'success',
            position: 'top',
          }).then(t => t.present());
        }
      }
    }
  }

  ngOnDestroy(): void { this.stop(); }
}
