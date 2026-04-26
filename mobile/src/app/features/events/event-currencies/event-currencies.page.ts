import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ToastController, LoadingController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { EventCurrency } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-event-currencies', templateUrl: 'event-currencies.page.html' })
export class EventCurrenciesPage implements OnInit {
  currencies: EventCurrency[] = [];
  loading = true;
  editingCode: string | null = null;
  newRate: number | null = null;

  constructor(private route: ActivatedRoute, private api: ApiService, private toastCtrl: ToastController, private loadingCtrl: LoadingController) {}

  get guid(): string { return this.route.snapshot.paramMap.get('guid')!; }

  ngOnInit(): void {
    this.api.getEventCurrencies(this.guid).subscribe({ next: r => { this.currencies = r.items; this.loading = false; }, error: () => { this.loading = false; } });
  }

  startEdit(code: string, current: number): void { this.editingCode = code; this.newRate = current; }
  cancelEdit(): void { this.editingCode = null; this.newRate = null; }

  async saveRate(currencyCode: string): Promise<void> {
    if (this.newRate === null) return;
    // Find currency GUID from code by using getCurrency lookup — API takes GUID not code
    // We use the code as the guid parameter in the rate endpoint
    const loading = await this.loadingCtrl.create({ message: 'Saving…' });
    await loading.present();
    this.api.setEventCurrencyRate(this.guid, currencyCode, this.newRate).subscribe({
      next: async () => {
        loading.dismiss();
        const c = this.currencies.find(x => x.currency_code === currencyCode);
        if (c) c.inCHF = this.newRate!;
        this.cancelEdit();
        const t = await this.toastCtrl.create({ message: 'Rate updated', duration: 2000, color: 'success' });
        await t.present();
      },
      error: async (e) => { loading.dismiss(); const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }
}
