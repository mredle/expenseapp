import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../../core/services/api.service';
import { Log } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-logs', templateUrl: 'logs.page.html' })
export class LogsPage implements OnInit {
  logs: Log[] = [];
  page = 1;
  hasNext = false;
  loading = true;
  severity = '';

  constructor(private api: ApiService) {}
  ngOnInit(): void { this.load(true); }

  load(reset = false): void {
    if (reset) { this.page = 1; this.logs = []; }
    this.loading = true;
    this.api.getLogs(this.page, 25, this.severity || undefined).subscribe({
      next: res => {
        this.logs = reset ? res.items : [...this.logs, ...res.items];
        this.hasNext = res.has_next;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  filterChange(): void { this.load(true); }

  loadMore(ev: any): void {
    if (!this.hasNext) { ev.target.complete(); return; }
    this.page++;
    this.api.getLogs(this.page, 25, this.severity || undefined).subscribe({
      next: res => { this.logs = [...this.logs, ...res.items]; this.hasNext = res.has_next; ev.target.complete(); },
      error: () => ev.target.complete(),
    });
  }

  severityColor(s: string): string {
    const map: Record<string, string> = { ERROR: 'danger', WARNING: 'warning', INFO: 'primary' };
    return map[s] ?? 'medium';
  }
}
