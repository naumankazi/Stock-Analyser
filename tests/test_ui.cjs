// Offline UI state checks: node --test tests/test_ui.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function createApp(fetch) {
    const context = vm.createContext({
        fetch, console: { log() {}, warn() {}, error() {} },
        setInterval: () => 1, clearInterval() {},
    });
    vm.runInContext(fs.readFileSync('app/static/js/app.js', 'utf8'), context);
    const app = context.app();
    app.$refs = {};
    app.$nextTick = () => {};
    return app;
}

const plain = value => JSON.parse(JSON.stringify(value));
const failedReport = {
    failed_tickers: ['KRMAYURVED.NS'],
    failure_reasons: { 'KRMAYURVED.NS': 'No data returned' },
    matched_tickers: [],
};

test('all three pages show their own failures and retain them across navigation', () => {
    const app = createApp();
    app.analysisFailures = [{ ticker: 'ANALYSIS.NS', reason: 'Timeout' }];
    app.queryReport = failedReport;
    app.screenerReport = { failed_tickers: ['SCREEN.NS'] };
    for (const [mode, ticker] of [
        ['query', 'KRMAYURVED.NS'], ['screener', 'SCREEN.NS'], ['analysis', 'ANALYSIS.NS'],
    ]) {
        app.switchMode(mode);
        assert.equal(app.currentFailures.length, 1);
        assert.equal(app.currentFailures[0].ticker, ticker);
        assert.ok(app.currentFailures[0].reason);
    }
});

test('query and screener show failures with zero matches and clear them on rerun', async () => {
    for (const [mode, run, report] of [
        ['query', 'runQuery', 'queryReport'], ['screener', 'runScreener', 'screenerReport'],
    ]) {
        let response = failedReport;
        const app = createApp(async () => {
            assert.equal(app[report], null);
            return { ok: true, json: async () => response };
        });
        app.queryText = 'Volume > Volume 1 month average';
        app.mode = mode;
        await app[run]();
        assert.equal(app.currentFailures[0].ticker, 'KRMAYURVED.NS');
        response = { failed_tickers: [], matched_tickers: [] };
        await app[run]();
        assert.equal(app.currentFailures.length, 0);
    }
});

test('analysis failure identifies the submitted ticker and successful retry clears it', async () => {
    let ok = false;
    const app = createApp(async () => {
        // Editing the input while a request is pending must not mislabel its failure.
        app.ticker = 'EDITED.NS';
        return { ok, json: async () => ok ? { meta: {} } : { detail: 'No data returned' } };
    });
    app.ticker = 'krmayurved.ns';
    await app.analyze();
    assert.deepEqual(plain(app.currentFailures), [
        { ticker: 'KRMAYURVED.NS', reason: 'No data returned' },
    ]);
    ok = true;
    app.ticker = 'KRMAYURVED.NS';
    await app.analyze();
    assert.equal(app.currentFailures.length, 0);
});

test('retry and edit actions open the selected ticker in analysis', () => {
    const app = createApp();
    app.mode = 'query';
    app.editFailedTicker('KRMAYURVED.NS');
    assert.equal(app.mode, 'analysis');
    assert.equal(app.ticker, 'KRMAYURVED.NS');
    let analyzed;
    app.analyze = () => { analyzed = app.ticker; };
    app.$nextTick = callback => callback();
    app.analyzeFromResults('RETRY.NS');
    assert.equal(analyzed, 'RETRY.NS');
});

test('analysis sends optional capital and risk inputs as numbers', async () => {
    let payload;
    const app = createApp(async (_url, request) => {
        payload = JSON.parse(request.body);
        return { ok: true, json: async () => ({}) };
    });
    app.ticker = 'TEST.NS';
    app.tradingCapital = '200000';
    app.analysisRiskPct = '0.75';
    await app.analyze();
    assert.equal(payload.trading_capital, 200000);
    assert.equal(payload.risk_pct, .75);
    app.tradingCapital = app.analysisRiskPct = '';
    await app.analyze();
    assert.equal(payload.trading_capital, null);
    assert.equal(payload.risk_pct, null);
});

test('swing table preserves unavailable fields and zero values', () => {
    const app = createApp();
    app.report = { meta: { currency_symbol: '₹' }, swing_data: { market_data: { current_price: 100, return_1m_pct: 0 } },
        swing_analysis: { stage: 'Stage 2', stage2_score: 0, entry_now: false, targets: [], sections: {} } };
    assert.equal(app.swingMarketRows.find(r => r.label === '1-month return').value, '0%');
    assert.equal(app.swingMarketRows.find(r => r.label === '10 EMA').value, 'Unavailable');
    assert.equal(app.swingSummaryRows.find(r => r.label === 'Stage-2 score /10').value, '0');
    assert.equal(app.swingSummaryRows.find(r => r.label === 'Technical stop').value, 'Unavailable');
    assert.equal(app.swingAnswers.length, 6);
    assert.equal(app.safeExternalUrl('javascript:alert(1)'), null);
});

test('single-stock page includes new swing tables and drops legacy trade-plan bindings', () => {
    const html = fs.readFileSync('app/static/index.html', 'utf8');
    assert.ok(html.includes('Swing decision table'));
    assert.ok(html.includes('Position sizing and trade management'));
    assert.ok(html.includes('Complete swing assessment'));
    assert.ok(!html.includes('report?.trade_levels'));
    assert.ok(!html.includes('report?.llm_analysis'));
});
