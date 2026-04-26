import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { InfiniteScrollCustomEvent, AlertController, ToastController, LoadingController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { Event, Post, EventUser } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-event-main', templateUrl: 'event-main.page.html' })
export class EventMainPage implements OnInit {
  event?: Event;
  posts: Post[] = [];
  eventUser?: EventUser;
  postsPage = 1;
  hasNextPosts = false;
  newPostBody = '';
  loading = true;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private api: ApiService,
    private auth: AuthService,
    private alertCtrl: AlertController,
    private toastCtrl: ToastController,
    private loadingCtrl: LoadingController,
  ) {}

  get guid(): string { return this.route.snapshot.paramMap.get('guid')!; }

  ngOnInit(): void { this.loadAll(); }

  loadAll(): void {
    this.loading = true;
    this.api.getEvent(this.guid).subscribe(ev => {
      this.event = ev;
      this.loading = false;
    });
    this.loadPosts(true);
    // resolve own event user
    const euGuid = this.auth.getEventUserGuid(this.guid);
    if (euGuid) {
      this.api.getEventUser(this.guid, euGuid).subscribe({ next: eu => this.eventUser = eu, error: () => {} });
    }
  }

  loadPosts(reset = false): void {
    if (reset) { this.postsPage = 1; this.posts = []; }
    this.api.getPosts(this.guid, this.postsPage).subscribe(res => {
      this.posts = reset ? res.items : [...this.posts, ...res.items];
      this.hasNextPosts = res.has_next;
    });
  }

  loadMorePosts(ev: InfiniteScrollCustomEvent): void {
    if (!this.hasNextPosts) { ev.target.complete(); return; }
    this.postsPage++;
    this.api.getPosts(this.guid, this.postsPage).subscribe({ next: res => { this.posts = [...this.posts, ...res.items]; this.hasNextPosts = res.has_next; ev.target.complete(); }, error: () => ev.target.complete() });
  }

  async submitPost(): Promise<void> {
    const body = this.newPostBody.trim();
    if (!body) return;
    const euGuid = this.auth.getEventUserGuid(this.guid) || undefined;
    this.api.createPost(this.guid, body, euGuid).subscribe({
      next: (p) => { this.posts = [p, ...this.posts]; this.newPostBody = ''; },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  async confirmClose(): Promise<void> {
    const alert = await this.alertCtrl.create({
      header: 'Close Event',
      message: 'Are you sure you want to close this event?',
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Close', handler: () => this.closeEvent() },
      ],
    });
    await alert.present();
  }

  closeEvent(): void {
    this.api.closeEvent(this.guid).subscribe({
      next: () => { if (this.event) this.event.closed = true; },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  reopenEvent(): void {
    this.api.reopenEvent(this.guid).subscribe({
      next: () => { if (this.event) this.event.closed = false; },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  requestBalance(): void {
    this.api.requestBalance(this.guid).subscribe({
      next: async () => { const t = await this.toastCtrl.create({ message: 'Balance report queued — check your email', duration: 3000, color: 'success' }); await t.present(); },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  goTo(path: string): void { this.router.navigate(['/event', this.guid, path]); }
}
