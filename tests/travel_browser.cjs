// Exercise the original workbench using isolated server storage.
const {chromium}=require('playwright');
const {service}=require('./browser_helpers.cjs');
const assert=require('node:assert/strict');
async function main(){
  const server=await service(8767); let browser;
  try {
    browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHANNEL ? {channel:process.env.PLAYWRIGHT_CHANNEL} : {})});
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('dialog',d=>d.accept());
    await page.goto('http://127.0.0.1:8767/');
    await page.locator('#entry-themes .chip').first().waitFor();
    assert.equal(await page.locator('#research-console').count(),0);
    await page.locator('#entry-themes .chip').filter({hasText:'把旅行总花费控制在可接受范围'}).click();
    await page.locator('#gen-count').fill('4');
    const generated=page.waitForResponse(r=>r.url().endsWith('/api/generate')&&r.ok());
    await page.locator('#btn-generate').click();
    const personas=await (await generated).json();
    assert.equal(personas.length,4);
    assert.ok(personas.every(p=>p.jtbd.job_id==='J3'));
    await page.locator('#gen-status').filter({hasText:'4 人'}).waitFor();
    await page.locator('#btn-sample').click();
    const campaign=await page.locator('#campaign-text').inputValue();
    assert.ok(campaign.includes('人均1200元'));
    await page.locator('#use-memory').check();
    const simulated=page.waitForResponse(r=>r.url().endsWith('/api/simulate')&&r.ok());
    await page.locator('#btn-simulate').click();
    const results=(await (await simulated).json()).results;
    assert.equal(results.length,4);
    await page.locator('#result-count').filter({hasText:'4'}).waitFor();
    assert.ok((await page.locator('#result-heatmap').innerText()).includes(personas[0].name));
    await page.locator('#persona-list').getByText(personas[1].name,{exact:false}).first().click();
    await page.locator('#persona-detail h2').filter({hasText:personas[1].name}).waitFor();
    await page.locator('#memory-timeline').filter({hasText:'周末两天'}).waitFor();
    const download=page.waitForEvent('download');
    await page.locator('#btn-export-excel').click();
    assert.ok((await download).suggestedFilename().endsWith('.xlsx'));
    const memory=page.waitForEvent('download');
    await page.locator('#btn-export-memories').click();
    assert.ok((await memory).suggestedFilename().endsWith('.json'));
    await page.goto('http://127.0.0.1:8767/jobs');
    await page.locator('#job-count').filter({hasText:'7 个主任务'}).waitFor();
    await page.goto('http://127.0.0.1:8767/admin');
    await page.locator('#factor-list .factor-row').first().waitFor();
    assert.equal(await page.locator('#factor-list .factor-row').count(),25);
    await page.setViewportSize({width:390,height:844});
    await page.goto('http://127.0.0.1:8767/');
    await page.locator('#persona-list').filter({hasText:personas[0].name}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);
    console.log('Original travel workbench browser regression passed.');
  } finally { if(browser)await browser.close(); server.kill(); }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
