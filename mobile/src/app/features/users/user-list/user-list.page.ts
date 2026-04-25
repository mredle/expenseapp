import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { InfiniteScrollCustomEvent, RefresherCustomEvent } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { User } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-user-list', templateUrl: 'user-list.page.html' })
export class UserListPage implements OnInit {
  users: User[] = [];
  page = 1;
  hasNext = false;
  loading = true;
  isAdmin = false;

  constructor(private api: ApiService, private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    this.loadCurrentUser();
    this.load(true);
  }

  private loadCurrentUser(): void {
    const guid = this.auth.userGuid;
    if (guid) {
      this.api.getUser(guid).subscribe({ next: u => { this.isAdmin = !!u.is_admin; } });
    }
  }

  load(reset = false): void {
    if (reset) { this.page = 1; this.users = []; }
    this.loading = true;
    this.api.getUsers(this.page).subscribe({
      next: res => {
        const newItems = res.items ?? [];
        this.users = reset ? newItems : [...this.users, ...newItems];
        this.hasNext = !!res._links?.next;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  refresh(ev: RefresherCustomEvent): void { this.load(true); ev.detail.complete(); }

  loadMore(ev: InfiniteScrollCustomEvent): void {
    if (!this.hasNext) { ev.target.complete(); return; }
    this.page++;
    this.api.getUsers(this.page).subscribe({
      next: res => {
        this.users = [...this.users, ...(res.items ?? [])];
        this.hasNext = !!res._links?.next;
        ev.target.complete();
      },
      error: () => ev.target.complete(),
    });
  }

  openUser(id: string): void { this.router.navigate(['/users', id]); }
}
