import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { FormBuilder, Validators } from '@angular/forms';
import { ToastController, InfiniteScrollCustomEvent, AlertController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { Settlement, Currency, EventUser } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-settlements', templateUrl: 'settlements.page.html' })
export class SettlementsPage implements OnInit {
  settlements: Settlement[] = [];
  currencies: Currency[] = [];
  eventUsers: EventUser[] = [];
  page = 1;
  hasNext = false;
  showForm = false;

  form = this.fb.group({
    recipient_id: [null, Validators.required],
    currency_id: [null, Validators.required],
    amount: [null, Validators.required],
    description: [''],
  });

  constructor(
    private route: ActivatedRoute, private fb: FormBuilder,
    private api: ApiService, private auth: AuthService,
    private toastCtrl: ToastController, private alertCtrl: AlertController,
  ) {}

  get guid(): string { return this.route.snapshot.paramMap.get('guid')!; }
  get euGuid(): string | undefined { return this.auth.getEventUserGuid(this.guid) || undefined; }

  ngOnInit(): void {
    this.api.getCurrencies(1, 100).subscribe(r => this.currencies = r.items);
    this.api.getEventUsers(this.guid, 1, 100).subscribe(r => this.eventUsers = r.items);
    this.load(true);
  }

  load(reset = false): void {
    if (reset) { this.page = 1; this.settlements = []; }
    this.api.getSettlements(this.guid, this.page, 25, undefined, this.euGuid).subscribe(res => {
      this.settlements = reset ? res.items : [...this.settlements, ...res.items];
      this.hasNext = res.has_next;
    });
  }

  loadMore(ev: InfiniteScrollCustomEvent): void {
    if (!this.hasNext) { ev.target.complete(); return; }
    this.page++;
    this.api.getSettlements(this.guid, this.page).subscribe({ next: res => { this.settlements = [...this.settlements, ...res.items]; this.hasNext = res.has_next; ev.target.complete(); }, error: () => ev.target.complete() });
  }

  async addSettlement(): Promise<void> {
    if (this.form.invalid) return;
    this.api.createSettlement(this.guid, this.form.value, this.euGuid).subscribe({
      next: s => { this.settlements = [s, ...this.settlements]; this.showForm = false; this.form.reset(); },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  async confirmSettlement(s: Settlement): Promise<void> {
    const alert = await this.alertCtrl.create({
      header: 'Confirm Payment', message: `Confirm payment of ${s.amount_str} ${s.currency_code}?`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Confirm', handler: () => this.api.confirmSettlement(this.guid, s.guid, this.euGuid).subscribe({ next: () => this.load(true), error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); } }) },
      ],
    });
    await alert.present();
  }

  async deleteSettlement(s: Settlement): Promise<void> {
    this.api.deleteSettlement(this.guid, s.guid, this.euGuid).subscribe({
      next: () => this.settlements = this.settlements.filter(x => x.guid !== s.guid),
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }
}
