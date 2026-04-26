import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ToastController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { Balance } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-balance', templateUrl: 'balance.page.html' })
export class BalancePage implements OnInit {
  balance?: Balance;
  loading = true;

  constructor(private route: ActivatedRoute, private api: ApiService, private toastCtrl: ToastController) {}

  get guid(): string { return this.route.snapshot.paramMap.get('guid')!; }

  ngOnInit(): void {
    this.api.getBalance(this.guid).subscribe({
      next: b => { this.balance = b; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  async requestPdf(): Promise<void> {
    this.api.requestBalance(this.guid).subscribe({
      next: async () => { const t = await this.toastCtrl.create({ message: 'Balance report queued — check your email', duration: 3000, color: 'success' }); await t.present(); },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }
}
