import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, Validators } from '@angular/forms';
import { LoadingController, ToastController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { Event, Currency } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-event-settings', templateUrl: 'event-settings.page.html' })
export class EventSettingsPage implements OnInit {
  event?: Event;
  currencies: Currency[] = [];
  isNew = false;

  form = this.fb.group({
    name: ['', Validators.required],
    date: ['', Validators.required],
    base_currency_id: [null as number | null, Validators.required],
    currency_ids: [[] as number[], Validators.required],
    exchange_fee: [0, Validators.required],
    accountant_id: [null as number | null],
    fileshare_link: [''],
    description: [''],
  });

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private api: ApiService,
    private loadingCtrl: LoadingController,
    private toastCtrl: ToastController,
  ) {}

  get guid(): string { return this.route.snapshot.paramMap.get('guid') || 'new'; }

  ngOnInit(): void {
    this.isNew = this.guid === 'new';
    this.api.getCurrencies(1, 100).subscribe(res => {
      this.currencies = res.items;
      if (!this.isNew) this.loadEvent();
    });
  }

  loadEvent(): void {
    this.api.getEvent(this.guid).subscribe(ev => {
      this.event = ev;
      // Find base currency ID by code
      const base = this.currencies.find(c => c.code === ev.base_currency_code);
      this.form.patchValue({
        name: ev.name,
        date: ev.date,
        base_currency_id: base ? base.id : null,
        exchange_fee: ev.exchange_fee,
        fileshare_link: ev.fileshare_link || '',
        description: ev.description || '',
      });
    });
  }

  async save(): Promise<void> {
    if (this.form.invalid) return;
    const loading = await this.loadingCtrl.create({ message: 'Saving…' });
    await loading.present();
    const data = this.form.value;
    const obs = this.isNew ? this.api.createEvent(data) : this.api.updateEvent(this.guid, data);
    obs.subscribe({
      next: (ev) => {
        loading.dismiss();
        this.router.navigate(['/event', ev.guid, 'main']);
      },
      error: async (e) => { loading.dismiss(); const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 3000, color: 'danger' }); await t.present(); },
    });
  }
}
