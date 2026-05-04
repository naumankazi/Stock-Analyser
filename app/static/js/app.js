/**
 * StockAnalyzer – Alpine.js application logic
 * LLM-optimized decision-layer UI — structured signals, no opinions.
 */

function app() {
    return {
        ticker: '',
        report: null,
        loading: false,
        error: null,
        theme: 'dark',
        loadingStep: '',
        chart: null,
        mode: 'analysis',
        includeLLMAnalysis: false,  // Toggle for LLM enrichment in single stock analysis

        // Query Filter state
        queryReport: null,
        queryLoading: false,
        queryError: null,
        queryText: '',
        queryUniverse: 'all_nse',
        queryTopN: 100,
        queryStep: '',
        queryMultiMode: false,  // Toggle for single vs multi-query mode
        includeLLM: false,      // Toggle for LLM enrichment
        llmMaxStocks: 15,       // Max stocks to enrich with LLM
        screenerUrls: '',       // Screener.in URLs to fetch stocks from (one per line)

        // Screener state
        screenerReport: null,
        screenerLoading: false,
        screenerError: null,
        screenerCapital: 100000,
        screenerRisk: 7.0,
        screenerTopN: 10,
        screenerCustomTickers: '',
        screenerStep: '',
        failedTickers: [],
        showFailedTickers: false,
        screenerIncludeLLM: false,   // Toggle for LLM enrichment in screener
        screenerLLMMaxStocks: 10,    // Max stocks to enrich with LLM in screener

        init() {
            const saved = localStorage.getItem('sa-theme');
            if (saved) {
                this.theme = saved;
                document.documentElement.setAttribute('data-theme', saved);
            }
        },

        switchMode(m) {
            this.mode = m;
        },

        /**
         * Navigate to single stock analysis from any tab.
         * Clears all state from previous tab and runs fresh analysis.
         * @param {string} tickerSymbol - The stock ticker to analyze
         * @param {boolean} withLLM - Whether to enable LLM enrichment (auto-enabled if coming from LLM context)
         */
        analyzeFromResults(tickerSymbol, withLLM = false) {
            // Clear state from previous analysis
            this.report = null;
            this.error = null;
            this.loading = false;
            this.loadingStep = '';
            
            // Set ticker and LLM preference
            this.ticker = tickerSymbol;
            if (withLLM) {
                this.includeLLMAnalysis = true;
            }
            
            // Switch to analysis mode and run fresh analysis
            this.mode = 'analysis';
            this.$nextTick(() => this.analyze());
        },

        // Toggle example query in multi-query mode (append/remove)
        toggleExampleQuery(query) {
            if (this.queryMultiMode) {
                const lines = this.queryText.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
                const idx = lines.findIndex(l => l === query);
                if (idx >= 0) {
                    // Remove if already present
                    lines.splice(idx, 1);
                } else {
                    // Append
                    lines.push(query);
                }
                this.queryText = lines.join('\n');
            } else {
                // Single query mode: replace
                this.queryText = query;
            }
        },

        // Check if a query is active (present in textarea)
        isQueryActive(query) {
            if (!this.queryMultiMode) {
                return this.queryText.trim() === query;
            }
            const lines = this.queryText.split(/\r?\n/).map(l => l.trim());
            return lines.includes(query);
        },

        // Toggle screener URL in the screenerUrls textarea (add/remove)
        toggleScreenerUrl(url) {
            const urls = this.screenerUrls.split(/\r?\n/).map(u => u.trim()).filter(u => u.length > 0);
            const idx = urls.findIndex(u => u === url);
            if (idx >= 0) {
                // Remove if already present
                urls.splice(idx, 1);
            } else {
                // Append
                urls.push(url);
            }
            this.screenerUrls = urls.join('\n');
        },

        // Check if a screener URL is active (present in textarea)
        isScreenerUrlActive(url) {
            const urls = this.screenerUrls.split(/\r?\n/).map(u => u.trim());
            return urls.includes(url);
        },

        toggleTheme() {
            this.theme = this.theme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', this.theme);
            localStorage.setItem('sa-theme', this.theme);
            if (this.report) {
                this.$nextTick(() => this.renderChart());
            }
        },

        async analyze() {
            if (!this.ticker.trim()) return;
            this.loading = true;
            this.error = null;
            this.report = null;

            const steps = this.includeLLMAnalysis ? [
                'Fetching market data...',
                'Computing indicators...',
                'Analyzing trends...',
                'Detecting patterns...',
                'Running AI analysis...',
                'Building report...',
            ] : [
                'Fetching market data...',
                'Computing indicators...',
                'Analyzing trends...',
                'Detecting patterns...',
                'Building report...',
            ];
            let stepIdx = 0;
            this.loadingStep = steps[0];
            const progressInterval = setInterval(() => {
                stepIdx = Math.min(stepIdx + 1, steps.length - 1);
                this.loadingStep = steps[stepIdx];
                if (this.$refs.progressBar) {
                    this.$refs.progressBar.style.width = Math.min(15 + stepIdx * 16, 90) + '%';
                }
            }, 1200);

            try {
                const res = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        ticker: this.ticker.trim(),
                        include_llm: this.includeLLMAnalysis 
                    }),
                });

                clearInterval(progressInterval);

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.detail || `HTTP ${res.status}`);
                }

                this.report = await res.json();
                this.$nextTick(() => this.renderChart());
            } catch (e) {
                console.error('[analyze] error:', e);
                this.error = e.message;
            } finally {
                this.loading = false;
                clearInterval(progressInterval);
            }
        },

        async runScreener() {
            this.screenerLoading = true;
            this.screenerError = null;
            this.screenerReport = null;
            this.failedTickers = [];
            this.showFailedTickers = false;

            const steps = this.screenerIncludeLLM ? [
                'Connecting to market data...',
                'Fetching fundamentals...',
                'Analyzing valuations...',
                'Computing growth metrics...',
                'Running technical checks...',
                'Scoring and ranking stocks...',
                'Running AI analysis on top stocks...',
                'Building portfolio allocation...',
            ] : [
                'Connecting to market data...',
                'Fetching fundamentals...',
                'Analyzing valuations...',
                'Computing growth metrics...',
                'Running technical checks...',
                'Scoring and ranking stocks...',
                'Building portfolio allocation...',
            ];
            let stepIdx = 0;
            this.screenerStep = steps[0];
            const progressInterval = setInterval(() => {
                stepIdx = Math.min(stepIdx + 1, steps.length - 1);
                this.screenerStep = steps[stepIdx];
                if (this.$refs.screenerProgressBar) {
                    this.$refs.screenerProgressBar.style.width = Math.min(10 + stepIdx * 13, 90) + '%';
                }
            }, 3000);

            try {
                const payload = {
                    capital: this.screenerCapital,
                    max_risk_pct: this.screenerRisk,
                    top_n: this.screenerTopN,
                    include_llm: this.screenerIncludeLLM,
                    llm_max_stocks: this.screenerLLMMaxStocks,
                };
                // Always include custom_tickers if provided (even if empty string, we'll check on backend)
                if (this.screenerCustomTickers && this.screenerCustomTickers.trim()) {
                    payload.custom_tickers = this.screenerCustomTickers.trim();
                    console.log('[runScreener] Custom tickers:', payload.custom_tickers);
                } else {
                    console.log('[runScreener] Using default universe');
                }
                console.log('[runScreener] Full payload:', JSON.stringify(payload, null, 2));
                const res = await fetch('/api/screen', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                clearInterval(progressInterval);

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.detail || `HTTP ${res.status}`);
                }

                const data = await res.json();
                this.screenerReport = data;
                
                // Extract failed tickers from the response if available
                if (data.failed_tickers && data.failed_tickers.length > 0) {
                    this.failedTickers = data.failed_tickers;
                    this.showFailedTickers = true;
                    console.warn('[runScreener] Failed tickers:', this.failedTickers);
                }
            } catch (e) {
                console.error('[runScreener] error:', e);
                this.screenerError = e.message;
            } finally {
                this.screenerLoading = false;
                clearInterval(progressInterval);
            }
        },

        async runQuery() {
            // Allow running if either query text or screener URLs are provided
            if (!this.queryText.trim() && !this.screenerUrls.trim()) return;
            
            this.queryLoading = true;
            this.queryError = null;
            this.queryReport = null;

            const hasScreenerUrls = this.screenerUrls.trim().length > 0;
            const urlCount = hasScreenerUrls ? this.screenerUrls.split(/\r?\n/).filter(u => u.trim()).length : 0;
            
            const steps = hasScreenerUrls ? [
                `Connecting to Screener.in (${urlCount} screen${urlCount > 1 ? 's' : ''})...`,
                'Fetching stocks from screen URLs...',
                'Pre-fetching price data in parallel...',
                'Computing technical indicators...',
                'Evaluating query conditions...',
                this.includeLLM ? 'Running AI analysis on top stocks...' : null,
                'Building results...',
            ].filter(Boolean) : (this.includeLLM ? [
                'Connecting to market data...',
                'Fetching stock universe...',
                'Pre-fetching price data in parallel...',
                'Computing technical indicators...',
                'Evaluating query conditions...',
                'Running AI analysis on top stocks...',
                'Building enriched results...',
            ] : [
                'Connecting to market data...',
                'Fetching stock universe...',
                'Pre-fetching price data in parallel...',
                'Computing technical indicators...',
                'Evaluating query conditions...',
                'Building results...',
            ]);
            let stepIdx = 0;
            this.queryStep = steps[0];
            const progressInterval = setInterval(() => {
                stepIdx = Math.min(stepIdx + 1, steps.length - 1);
                this.queryStep = steps[stepIdx];
                if (this.$refs.queryProgressBar) {
                    this.$refs.queryProgressBar.style.width = Math.min(10 + stepIdx * 15, 90) + '%';
                }
            }, 4000);

            try {
                let payload;
                
                // Parse screener URLs (one per line)
                const screenerUrlList = this.screenerUrls.split(/\r?\n/)
                    .map(u => u.trim())
                    .filter(u => u.length > 0 && u.startsWith('http'));
                
                // Build base payload with optional screener_urls
                const basePayload = {
                    universe: this.queryUniverse,
                    top_n: this.queryTopN,
                    include_llm: this.includeLLM,
                    llm_max_stocks: this.llmMaxStocks,
                };
                
                // Add screener_urls if provided (use array for multiple, single string for one)
                if (screenerUrlList.length > 1) {
                    basePayload.screener_urls = screenerUrlList;
                } else if (screenerUrlList.length === 1) {
                    basePayload.screener_url = screenerUrlList[0];
                }
                
                const hasScreenerUrls = screenerUrlList.length > 0;
                
                if (this.queryMultiMode) {
                    // Multi-query mode: split by newlines (handle both \r\n and \n), filter empty
                    const queries = this.queryText.split(/\r?\n/)
                        .map(q => q.trim())
                        .filter(q => q.length > 0 && !q.startsWith('#'));
                    
                    if (queries.length === 0 && !hasScreenerUrls) {
                        throw new Error('Please enter at least one query or provide Screener.in URL(s)');
                    }
                    
                    payload = {
                        ...basePayload,
                        queries: queries.length > 0 ? queries : undefined,
                    };
                    console.log('[runQuery] Multi-query mode:', queries.length, 'queries, LLM:', this.includeLLM, 'screenerUrls:', screenerUrlList.length);
                } else {
                    // Single query mode
                    if (!this.queryText.trim() && !hasScreenerUrls) {
                        throw new Error('Please enter a query or provide Screener.in URL(s)');
                    }
                    payload = {
                        ...basePayload,
                        query: this.queryText.trim() || undefined,
                    };
                }
                console.log('[runQuery] Payload:', JSON.stringify(payload, null, 2));
                
                const res = await fetch('/api/screen', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                clearInterval(progressInterval);

                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.detail || `HTTP ${res.status}`);
                }

                const data = await res.json();
                this.queryReport = data;
                console.log('[runQuery] Results:', data.matched_tickers?.length, 'matched');
                
            } catch (e) {
                console.error('[runQuery] error:', e);
                this.queryError = e.message;
            } finally {
                this.queryLoading = false;
                clearInterval(progressInterval);
            }
        },

        useInScreener() {
            if (!this.queryReport?.matched_tickers?.length) return;
            
            // Transfer matched tickers to screener
            const tickers = this.queryReport.matched_tickers.join(',');
            const tickerCount = this.queryReport.matched_tickers.length;
            this.screenerCustomTickers = tickers;
            
            // Clear query state
            this.queryReport = null;
            
            // Switch to screener mode
            this.switchMode('screener');
            
            console.log('[useInScreener] Transferred', tickerCount, 'tickers to screener');
        },

        renderChart() {
          try {
            const container = document.getElementById('chart-container');
            if (!container || !this.report?.chart_data?.length) return;

            container.innerHTML = '';

            const isDark = this.theme === 'dark';
            const chartOptions = {
                width: container.clientWidth,
                height: 400,
                layout: {
                    background: { color: isDark ? '#1c2128' : '#ffffff' },
                    textColor: isDark ? '#8b949e' : '#656d76',
                },
                grid: {
                    vertLines: { color: isDark ? '#21262d' : '#f0f0f0' },
                    horzLines: { color: isDark ? '#21262d' : '#f0f0f0' },
                },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: isDark ? '#30363d' : '#d0d7de' },
                timeScale: { borderColor: isDark ? '#30363d' : '#d0d7de', timeVisible: false },
            };

            this.chart = LightweightCharts.createChart(container, chartOptions);

            const candleSeries = this.chart.addCandlestickSeries({
                upColor: '#3fb950',
                downColor: '#f85149',
                borderDownColor: '#f85149',
                borderUpColor: '#3fb950',
                wickDownColor: '#f85149',
                wickUpColor: '#3fb950',
            });
            candleSeries.setData(this.report.chart_data);

            const volumeSeries = this.chart.addHistogramSeries({
                priceFormat: { type: 'volume' },
                priceScaleId: '',
            });
            volumeSeries.priceScale().applyOptions({
                scaleMargins: { top: 0.8, bottom: 0 },
            });
            const volData = this.report.chart_data.map(d => ({
                time: d.time,
                value: d.volume,
                color: d.close >= d.open ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)',
            }));
            volumeSeries.setData(volData);

            // MA lines
            if (this.report.trend_structure?.ma_50) {
                this.addMALine(candleSeries, 50, '#58a6ff');
            }
            if (this.report.trend_structure?.ma_200) {
                this.addMALine(candleSeries, 200, '#d29922');
            }

            // Bollinger Bands
            this.addBBLines(candleSeries);

            // S/R lines
            if (this.report.support_resistance) {
                this.report.support_resistance.support_levels.forEach(level => {
                    candleSeries.createPriceLine({ price: level, color: '#3fb950', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'S' });
                });
                this.report.support_resistance.resistance_levels.forEach(level => {
                    candleSeries.createPriceLine({ price: level, color: '#f85149', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'R' });
                });
            }

            // Trade level lines
            if (this.report.trade_levels) {
                const tl = this.report.trade_levels;
                candleSeries.createPriceLine({ price: tl.ideal_entry, color: '#58a6ff', lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: 'Entry' });
                tl.targets.forEach(t => {
                    candleSeries.createPriceLine({ price: t.price, color: '#3fb950', lineWidth: 1, lineStyle: 1, axisLabelVisible: true, title: t.label });
                });
                tl.stop_losses.forEach(sl => {
                    candleSeries.createPriceLine({ price: sl.price, color: '#f85149', lineWidth: 1, lineStyle: 1, axisLabelVisible: true, title: sl.label });
                });
            }

            this.chart.timeScale().fitContent();

            const resizeObserver = new ResizeObserver(() => {
                if (this.chart) {
                    this.chart.applyOptions({ width: container.clientWidth });
                }
            });
            resizeObserver.observe(container);
          } catch (e) {
            console.error('[renderChart] error:', e);
          }
        },

        addMALine(candleSeries, period, color) {
          try {
            const data = this.report.chart_data;
            if (data.length < period) return;

            const maData = [];
            for (let i = period - 1; i < data.length; i++) {
                let sum = 0;
                for (let j = i - period + 1; j <= i; j++) {
                    sum += data[j].close;
                }
                maData.push({ time: data[i].time, value: sum / period });
            }

            const maSeries = this.chart.addLineSeries({
                color: color,
                lineWidth: 1,
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
            });
            maSeries.setData(maData);
          } catch (e) {
            console.error(`[addMALine] period=${period} error:`, e);
          }
        },

        addBBLines(candleSeries) {
          try {
            const data = this.report.chart_data;
            const period = 20;
            if (data.length < period) return;

            const upper = [], middle = [], lower = [];
            for (let i = period - 1; i < data.length; i++) {
                const slice = data.slice(i - period + 1, i + 1).map(d => d.close);
                const mean = slice.reduce((a, b) => a + b, 0) / period;
                const std = Math.sqrt(slice.reduce((sum, v) => sum + (v - mean) ** 2, 0) / period);
                const t = data[i].time;
                upper.push({ time: t, value: mean + 2 * std });
                middle.push({ time: t, value: mean });
                lower.push({ time: t, value: mean - 2 * std });
            }

            const addLine = (lineData, color, dash) => {
                const s = this.chart.addLineSeries({
                    color: color,
                    lineWidth: 1,
                    lineStyle: dash ? 2 : 0,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });
                s.setData(lineData);
            };

            addLine(upper, 'rgba(188,140,255,0.5)', true);
            addLine(middle, 'rgba(188,140,255,0.3)', false);
            addLine(lower, 'rgba(188,140,255,0.5)', true);
          } catch (e) {
            console.error('[addBBLines] error:', e);
          }
        },

        // ── UI Helpers ────────────────────────────────────

        trendBadge(direction) {
            const d = (direction || '').toLowerCase();
            if (d === 'bullish') return 'badge-green';
            if (d === 'bearish') return 'badge-red';
            return 'badge-yellow';
        },

        marketStateBadge() {
            const s = this.report?.quant_scores?.market_state || '';
            if (s.includes('bullish')) return 'badge-green';
            if (s.includes('bearish')) return 'badge-red';
            return 'badge-yellow';
        },

        capitalize(str) {
            if (!str) return '';
            return str.charAt(0).toUpperCase() + str.slice(1);
        },

        rsiBadge() {
            const z = this.report?.momentum_signals?.rsi_state;
            if (z?.includes('overbought')) return 'badge-red';
            if (z?.includes('oversold')) return 'badge-green';
            if (z?.includes('bullish')) return 'badge-green';
            if (z?.includes('bearish')) return 'badge-red';
            return 'badge-yellow';
        },

        rsiColor() {
            const v = this.report?.momentum_signals?.rsi || 50;
            if (v >= 70) return 'var(--accent-red)';
            if (v <= 30) return 'var(--accent-green)';
            return 'var(--accent-blue)';
        },

        fibWidth(key) {
            const pct = parseFloat(key);
            return isNaN(pct) ? 50 : Math.max(pct, 5);
        },

        fibColor(key) {
            const pct = parseFloat(key);
            if (pct <= 23.6) return 'var(--accent-green)';
            if (pct <= 50) return 'var(--accent-blue)';
            if (pct <= 61.8) return 'var(--accent-yellow)';
            return 'var(--accent-red)';
        },

        formatNum(n) {
            if (!n) return '0';
            if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
            if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
            if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
            return n.toLocaleString();
        },

        cs() {
            return this.report?.meta?.currency_symbol || '$';
        },
    };
}
