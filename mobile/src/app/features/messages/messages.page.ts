import { Component, OnInit, OnDestroy } from '@angular/core';
import { RefresherCustomEvent } from '@ionic/angular';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Message, User } from '../../core/models/models';

@Component({ standalone: false, selector: 'app-messages', templateUrl: 'messages.page.html' })
export class MessagesPage implements OnInit {
  messages: Message[] = [];
  loading = true;
  composing = false;
  users: User[] = [];
  recipientId: number | null = null;
  composeBody = '';
  sending = false;

  constructor(private api: ApiService, private auth: AuthService) {}

  ngOnInit(): void { this.load(); this.loadUsers(); }

  load(): void {
    this.loading = true;
    this.api.getMessages(1, 50).subscribe({
      next: res => { this.messages = res.items; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  loadUsers(): void {
    this.api.getUsers(1, 200).subscribe({
      next: res => { this.users = res.items ?? []; },
    });
  }

  refresh(ev: RefresherCustomEvent): void { this.load(); ev.detail.complete(); }

  openCompose(): void { this.composing = true; this.recipientId = null; this.composeBody = ''; }
  cancelCompose(): void { this.composing = false; }

  send(): void {
    if (!this.recipientId || !this.composeBody.trim()) { return; }
    this.sending = true;
    this.api.sendMessage(this.recipientId, this.composeBody.trim()).subscribe({
      next: () => { this.sending = false; this.composing = false; this.load(); },
      error: () => { this.sending = false; },
    });
  }
}
