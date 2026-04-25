import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { AlertController, ToastController } from '@ionic/angular';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Currency } from '../../core/models/models';

@Component({ standalone: false, selector: 'app-currencies', templateUrl: 'currencies.page.html' })
export class CurrenciesPage implements OnInit {
  currencies: Currency[] = [];
  loading = true;
  showForm = false;
  editingGuid: string | null = null;
  form: FormGroup;
  isAdmin = false;

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private fb: FormBuilder,
    private alert: AlertController,
    private toast: ToastController,
  ) {
    this.form = this.fb.group({
      code: ['', [Validators.required, Validators.maxLength(10)]],
      name: ['', Validators.required],
      number: [null],
      exponent: [2],
      inCHF: [1, Validators.required],
      description: [''],
    });
  }

  ngOnInit(): void {
    this.loadCurrentUser();
    this.load();
  }

  private loadCurrentUser(): void {
    const guid = this.auth.userGuid;
    if (guid) {
      this.api.getUser(guid).subscribe({ next: u => { this.isAdmin = !!u.is_admin; } });
    }
  }

  load(): void {
    this.loading = true;
    this.api.getCurrencies(1, 200).subscribe({
      next: res => { this.currencies = res.items; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  startAdd(): void {
    this.editingGuid = null;
    this.form.reset({ exponent: 2, inCHF: 1 });
    this.showForm = true;
  }

  startEdit(c: Currency): void {
    this.editingGuid = c.guid;
    this.form.patchValue(c);
    this.showForm = true;
  }

  cancelForm(): void { this.showForm = false; }

  submit(): void {
    if (this.form.invalid) { return; }
    const data = this.form.value;
    const op$ = this.editingGuid
      ? this.api.updateCurrency(this.editingGuid, data)
      : this.api.createCurrency(data);
    op$.subscribe({
      next: () => { this.showForm = false; this.load(); this.showToast(this.editingGuid ? 'Currency updated.' : 'Currency created.'); },
      error: () => this.showToast('Error saving currency.', true),
    });
  }

  confirmDelete(c: Currency): void {
    this.alert.create({
      header: 'Delete Currency',
      message: `Delete ${c.code} – ${c.name}?`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Delete', role: 'destructive', handler: () => this.deleteCurrency(c.guid) },
      ],
    }).then(a => a.present());
  }

  private deleteCurrency(guid: string): void {
    // Currencies API does not expose DELETE — show info toast
    this.showToast('Currency deletion is not supported via the API.', true);
  }

  private showToast(msg: string, error = false): void {
    this.toast.create({ message: msg, duration: 2500, color: error ? 'danger' : 'success', position: 'bottom' })
      .then(t => t.present());
  }
}
