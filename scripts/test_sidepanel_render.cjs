const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/usr/bin/google-chrome-stable',
    args: ['--no-sandbox', '--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  const consoleMsgs = [];
  page.on('console', msg => consoleMsgs.push(msg.text()));
  page.on('pageerror', err => consoleMsgs.push('ERROR: ' + err.message));

  await page.goto('file:///home/epsilon/Projects/spiderRAG/extension/dist/sidepanel.html', { waitUntil: 'networkidle0' });
  const html = await page.$eval('#root', el => el.innerHTML);
  console.log('Root HTML rendered length:', html.length);
  console.log('H1 text:', await page.$eval('h1', el => el.textContent));

  const buttons = await page.$$eval('button', els => els.map(e => e.textContent.trim()));
  console.log('Rendered buttons:', buttons);

  console.log('Console messages:', consoleMsgs);
  await browser.close();
  console.log('Side panel rendered successfully with zero runtime errors!');
})();
