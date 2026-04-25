import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../../core/services/api.service';
import { Stat } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-statistics', templateUrl: 'statistics.page.html' })
export class StatisticsPage implements OnInit {
  stats: Stat[] = [];
  loading = true;

  constructor(private api: ApiService) {}
  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading = true;
    this.api.getStatistics().subscribe({
      next: res => { this.stats = res.items; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }
}
