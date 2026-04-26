import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ToastController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { Expense, EventUser } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-expense-detail', templateUrl: 'expense-detail.page.html' })
export class ExpenseDetailPage implements OnInit {
  expense?: Expense;
  affectedUsers: EventUser[] = [];
  allUsers: EventUser[] = [];
  loading = true;

  constructor(private route: ActivatedRoute, private api: ApiService, private toastCtrl: ToastController) {}

  get eventGuid(): string { return this.route.snapshot.paramMap.get('guid')!; }
  get expenseGuid(): string { return this.route.snapshot.paramMap.get('expenseGuid')!; }

  ngOnInit(): void {
    this.api.getExpense(this.eventGuid, this.expenseGuid).subscribe(e => { this.expense = e; this.loading = false; });
    this.api.getExpenseUsers(this.eventGuid, this.expenseGuid).subscribe(r => this.affectedUsers = r.items);
    this.api.getEventUsers(this.eventGuid, 1, 100).subscribe(r => this.allUsers = r.items);
  }

  async addUser(userGuid: string): Promise<void> {
    this.api.addExpenseUser(this.eventGuid, this.expenseGuid, userGuid).subscribe({
      next: () => this.api.getExpenseUsers(this.eventGuid, this.expenseGuid).subscribe(r => this.affectedUsers = r.items),
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  async removeUser(userGuid: string): Promise<void> {
    this.api.removeExpenseUser(this.eventGuid, this.expenseGuid, userGuid).subscribe({
      next: () => this.affectedUsers = this.affectedUsers.filter(u => u.guid !== userGuid),
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  isAffected(guid: string): boolean { return this.affectedUsers.some(u => u.guid === guid); }

  async uploadReceipt(event: any): Promise<void> {
    const file: File = event.target.files[0];
    if (!file) return;
    this.api.uploadReceipt(this.eventGuid, this.expenseGuid, file).subscribe({
      next: async (img) => { if (this.expense) this.expense.image_url = img.url; const t = await this.toastCtrl.create({ message: 'Receipt uploaded', duration: 2000, color: 'success' }); await t.present(); },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Upload failed', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }
}
