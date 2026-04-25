import { Component } from '@angular/core';
import { NotificationService } from '../../core/services/notification.service';

@Component({ standalone: false, selector: 'app-tabs', templateUrl: 'tabs.page.html' })
export class TabsPage {
  unreadCount$ = this.notifications.unreadCount$;

  constructor(private notifications: NotificationService) {}
}
