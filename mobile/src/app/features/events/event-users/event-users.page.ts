import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, Validators } from '@angular/forms';
import { ToastController, AlertController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { EventUser } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-event-users', templateUrl: 'event-users.page.html' })
export class EventUsersPage implements OnInit {
  users: EventUser[] = [];
  showForm = false;
  form = this.fb.group({
    username: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    weighting: [1.0, Validators.required],
    locale: ['en'],
    about_me: [''],
  });

  constructor(
    private route: ActivatedRoute, private router: Router, private fb: FormBuilder,
    private api: ApiService, private toastCtrl: ToastController, private alertCtrl: AlertController,
  ) {}

  get guid(): string { return this.route.snapshot.paramMap.get('guid')!; }

  ngOnInit(): void { this.api.getEventUsers(this.guid, 1, 100).subscribe(r => this.users = r.items); }

  async addUser(): Promise<void> {
    if (this.form.invalid) return;
    this.api.addEventUser(this.guid, this.form.value).subscribe({
      next: u => { this.users = [...this.users, u]; this.showForm = false; this.form.reset({ weighting: 1.0, locale: 'en' }); },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  viewUser(userGuid: string): void { this.router.navigate(['/event', this.guid, 'users', userGuid]); }

  async removeUser(user: EventUser): Promise<void> {
    const alert = await this.alertCtrl.create({
      header: 'Remove User', message: `Remove ${user.username} from the event?`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Remove', role: 'destructive', handler: () => this.api.removeEventUser(this.guid, user.guid).subscribe({ next: () => this.users = this.users.filter(u => u.guid !== user.guid), error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); } }) },
      ],
    });
    await alert.present();
  }
}
