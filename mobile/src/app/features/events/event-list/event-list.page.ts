import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { InfiniteScrollCustomEvent, RefresherCustomEvent } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { Event } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-event-list', templateUrl: 'event-list.page.html' })
export class EventListPage implements OnInit {
  events: Event[] = [];
  page = 1;
  hasNext = false;
  loading = true;

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void { this.load(true); }

  load(reset = false): void {
    if (reset) { this.page = 1; this.events = []; }
    this.loading = true;
    this.api.getEvents(this.page).subscribe({
      next: res => {
        this.events = reset ? res.items : [...this.events, ...res.items];
        this.hasNext = res.has_next;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  refresh(ev: RefresherCustomEvent): void {
    this.load(true);
    ev.detail.complete();
  }

  loadMore(ev: InfiniteScrollCustomEvent): void {
    if (!this.hasNext) { ev.target.complete(); return; }
    this.page++;
    this.api.getEvents(this.page).subscribe({
      next: res => {
        this.events = [...this.events, ...res.items];
        this.hasNext = res.has_next;
        ev.target.complete();
      },
      error: () => ev.target.complete(),
    });
  }

  openEvent(guid: string): void { this.router.navigate(['/event', guid, 'main']); }
  newEvent(): void { this.router.navigate(['/event', 'new', 'settings']); }
}
