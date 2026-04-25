import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { FormBuilder, Validators } from '@angular/forms';
import { ToastController, LoadingController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { EventUser } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-event-user-detail', templateUrl: 'event-user-detail.page.html' })
export class EventUserDetailPage implements OnInit {
  eventUser?: EventUser;
  editMode = false;
  bankMode = false;

  profileForm = this.fb.group({
    username: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    weighting: [1.0, Validators.required],
    about_me: [''],
    locale: ['en'],
  });

  bankForm = this.fb.group({
    iban: [''], bank: [''], name: [''], address: [''],
    address_suffix: [''], zip_code: [null], city: [''], country: [''],
  });

  constructor(
    private route: ActivatedRoute, private fb: FormBuilder,
    private api: ApiService, private toastCtrl: ToastController, private loadingCtrl: LoadingController,
  ) {}

  get eventGuid(): string { return this.route.snapshot.paramMap.get('guid')!; }
  get userGuid(): string { return this.route.snapshot.paramMap.get('userGuid')!; }

  ngOnInit(): void {
    this.api.getEventUser(this.eventGuid, this.userGuid).subscribe(u => {
      this.eventUser = u;
      this.profileForm.patchValue({ username: u.username, email: u.email, weighting: u.weighting, about_me: u.about_me || '', locale: u.locale });
    });
  }

  async saveProfile(): Promise<void> {
    if (this.profileForm.invalid) return;
    const loading = await this.loadingCtrl.create({ message: 'Saving…' });
    await loading.present();
    this.api.updateEventUserProfile(this.eventGuid, this.userGuid, this.profileForm.value).subscribe({
      next: u => { loading.dismiss(); this.eventUser = u; this.editMode = false; },
      error: async (e) => { loading.dismiss(); const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  async saveBank(): Promise<void> {
    const loading = await this.loadingCtrl.create({ message: 'Saving…' });
    await loading.present();
    this.api.updateEventUserBank(this.eventGuid, this.userGuid, this.bankForm.value).subscribe({
      next: () => { loading.dismiss(); this.bankMode = false; },
      error: async (e) => { loading.dismiss(); const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  async uploadPicture(event: any): Promise<void> {
    const file: File = event.target.files[0];
    if (!file) return;
    this.api.uploadEventUserPicture(this.eventGuid, this.userGuid, file).subscribe({
      next: async img => { if (this.eventUser) this.eventUser.avatar = img.url; const t = await this.toastCtrl.create({ message: 'Picture updated', duration: 2000, color: 'success' }); await t.present(); },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Upload failed', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }
}
