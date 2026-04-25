import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ActionSheetController, AlertController, ToastController, InfiniteScrollCustomEvent } from '@ionic/angular';
import { FormBuilder, Validators } from '@angular/forms';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { Expense, Currency, EventUser } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-expenses', templateUrl: 'expenses.page.html' })
export class ExpensesPage implements OnInit {
  expenses: Expense[] = [];
  currencies: Currency[] = [];
  eventUsers: EventUser[] = [];
  page = 1;
  hasNext = false;
  showForm = false;
  filterOwn = false;

  form = this.fb.group({
    currency_id: [null, Validators.required],
    amount: [null, Validators.required],
    affected_user_ids: [[] as number[], Validators.required],
    date: [new Date().toISOString().split('T')[0], Validators.required],
    description: [''],
  });

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private api: ApiService,
    private auth: AuthService,
    private actionSheetCtrl: ActionSheetController,
    private alertCtrl: AlertController,
    private toastCtrl: ToastController,
  ) {}

  get guid(): string { return this.route.snapshot.paramMap.get('guid')!; }
  get euGuid(): string | undefined { return this.auth.getEventUserGuid(this.guid) || undefined; }

  ngOnInit(): void {
    this.api.getCurrencies(1, 100).subscribe(r => this.currencies = r.items);
    this.api.getEventUsers(this.guid, 1, 100).subscribe(r => this.eventUsers = r.items);
    this.load(true);
  }

  load(reset = false): void {
    if (reset) { this.page = 1; this.expenses = []; }
    this.api.getExpenses(this.guid, this.page, 25, this.filterOwn, this.euGuid).subscribe(res => {
      this.expenses = reset ? res.items : [...this.expenses, ...res.items];
      this.hasNext = res.has_next;
    });
  }

  loadMore(ev: InfiniteScrollCustomEvent): void {
    if (!this.hasNext) { ev.target.complete(); return; }
    this.page++;
    this.api.getExpenses(this.guid, this.page, 25, this.filterOwn, this.euGuid).subscribe({ next: res => { this.expenses = [...this.expenses, ...res.items]; this.hasNext = res.has_next; ev.target.complete(); }, error: () => ev.target.complete() });
  }

  async addExpense(): Promise<void> {
    if (this.form.invalid) return;
    const data = this.form.value;
    this.api.createExpense(this.guid, data, this.euGuid).subscribe({
      next: (e) => { this.expenses = [e, ...this.expenses]; this.showForm = false; this.form.reset({ date: new Date().toISOString().split('T')[0], affected_user_ids: [] }); },
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }

  openExpense(expenseGuid: string): void { this.router.navigate(['/event', this.guid, 'expenses', expenseGuid]); }

  async expenseActions(expense: Expense): Promise<void> {
    const sheet = await this.actionSheetCtrl.create({
      header: expense.description || 'Expense',
      buttons: [
        { text: 'View / Edit Users', handler: () => this.openExpense(expense.guid) },
        { text: 'Delete', role: 'destructive', handler: () => this.deleteExpense(expense) },
        { text: 'Cancel', role: 'cancel' },
      ],
    });
    await sheet.present();
  }

  deleteExpense(expense: Expense): void {
    this.api.deleteExpense(this.guid, expense.guid, this.euGuid).subscribe({
      next: () => this.expenses = this.expenses.filter(e => e.guid !== expense.guid),
      error: async (e) => { const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 2000, color: 'danger' }); await t.present(); },
    });
  }
}
