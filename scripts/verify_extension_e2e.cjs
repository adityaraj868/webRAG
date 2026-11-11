const puppeteer = require('puppeteer');
const path = require('path');

async function testExtension() {
  console.log('[E2E Test] Starting Chrome with WebRAG extension...');
  const extensionPath = path.resolve(__dirname, '../extension/dist');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/usr/bin/google-chrome-stable',
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
    ],
  });

  try {
    // 1. Wait for service worker
    console.log('[E2E Test] Waiting for extension service worker...');
    const workerTarget = await browser.waitForTarget(
      (target) => target.type() === 'service_worker',
      { timeout: 8000 }
    );
    console.log('[E2E Test] ✅ Service Worker target discovered:', workerTarget.url());

    // 2. Extract extension ID from service worker URL (chrome-extension://<id>/service-worker.js)
    const swUrl = workerTarget.url();
    const extensionId = swUrl.split('/')[2];
    console.log('[E2E Test] Extension ID:', extensionId);

    // 3. Open sidepanel.html page directly
    const sidepanelUrl = `chrome-extension://${extensionId}/sidepanel.html`;
    console.log(`[E2E Test] Opening sidepanel page: ${sidepanelUrl}`);
    const page = await browser.newPage();

    const consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    page.on('pageerror', (err) => {
      consoleErrors.push(err.message);
    });

    await page.goto(sidepanelUrl, { waitUntil: 'networkidle0', timeout: 10000 });

    // 4. Verify React root and UI rendering
    await page.waitForSelector('#root', { timeout: 5000 });
    const titleText = await page.$eval('h1', (el) => el.textContent);
    console.log(`[E2E Test] ✅ WebRAG Header rendered with text: "${titleText}"`);

    // Verify mode buttons exist
    const buttons = await page.$$eval('button', (els) => els.map((e) => e.textContent.trim()));
    console.log('[E2E Test] Discovered UI buttons:', buttons);

    const hasCurrentPage = buttons.some((b) => b.includes('Current Page'));
    const hasEntireWebsite = buttons.some((b) => b.includes('Entire Website'));

    if (!hasCurrentPage || !hasEntireWebsite) {
      throw new Error('Mode selector buttons not found in rendered DOM');
    }
    console.log('[E2E Test] ✅ Mode selector rendered successfully');

    if (consoleErrors.length > 0) {
      console.warn('[E2E Test] Page console errors:', consoleErrors);
      // Fail only on fatal errors, not network offline warnings
      const fatalErrors = consoleErrors.filter((e) => !e.includes('Failed to fetch') && !e.includes('Cannot connect'));
      if (fatalErrors.length > 0) {
        throw new Error(`Fatal JavaScript errors in sidepanel: ${fatalErrors.join(', ')}`);
      }
    }

    console.log('[E2E Test] ✅ Extension UI, React 19 mount, and Side Panel loaded without runtime errors!');
  } finally {
    await browser.close();
  }
}

testExtension()
  .then(() => {
    console.log('[E2E Test] 🎉 All Chrome extension browser tests PASSED!');
    process.exit(0);
  })
  .catch((err) => {
    console.error('[E2E Test] ❌ Test failed:', err);
    process.exit(1);
  });
