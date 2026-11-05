// Headless regression for the restored travel generation and analysis workbench.
const {chromium}=require('playwright');
const {service}=require('./browser_helpers.cjs');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
async function main(){
  const server=await service(8767);let browser;
  try{
    browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHANNEL ? {channel:process.env.PLAYWRIGHT_CHANNEL} : {})});
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:8767/');
    assert.equal(await page.locator('#agent-analysis').count(),1);
    assert.ok(!(await page.locator('body').innerText()).includes('沿用 JTBD 旧分析逻辑'));
    let releaseResponse,requests=0,fail=false;
    const responseGate=new Promise(resolve=>releaseResponse=resolve);
    await page.route('**/api/simulate',async route=>{
      requests++;
      if(fail){await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'测试请求失败'})});return;}
      const response=await route.fetch();
      if(requests===1)await responseGate;
      await route.fulfill({response});
    });
    await page.locator('#count').fill('3');
    await page.locator('#generate').click();
    await page.locator('.persona-card').nth(2).waitFor();
    assert.equal(await page.locator('.persona-card').count(),3);
    await page.locator('#campaign').fill('周末短途旅行方案，费用包含交通与住宿，可免费改期。');
    await page.locator('#simulate').click();
    await page.locator('[data-flow=plan][data-state=active]').waitFor();
    assert.equal(await page.locator('[data-state=pending]').count(),3);
    assert.equal(await page.locator('#analysis-progress').getAttribute('aria-valuenow'),'0');
    assert.equal(await page.locator('.result-card').count(),0);
    assert.equal(await page.locator('#simulate').isDisabled(),true);
    assert.equal(await page.locator('[data-flow=plan]>span').evaluate(el=>getComputedStyle(el).animationName),'flow-pulse');
    if(process.env.SCREENSHOT_DIR){
      fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});
      await page.locator('#agent-analysis').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'travel-agent-analysis-running.png')});
    }
    releaseResponse();
    await page.locator('[data-flow=factors][data-state=active]').waitFor();
    assert.equal(await page.locator('[aria-current=step]').count(),1);
    assert.equal(await page.locator('#analysis-progress').getAttribute('aria-valuenow'),'1');
    await page.locator('.result-card').nth(2).waitFor();
    await page.locator('#agent-analysis [data-state=complete]').nth(3).waitFor();
    assert.ok((await page.locator('#agent-analysis').innerText()).includes('命中'));
    assert.ok((await page.locator('#agent-analysis-count').innerText()).includes('3 个画像'));
    assert.equal(await page.locator('.result-card').count(),3);
    assert.equal(await page.locator('#analysis-progress').getAttribute('aria-valuenow'),'4');
    assert.equal(await page.locator('[aria-current=step]').count(),0);
    await page.locator('#replay-analysis').click();
    await page.locator('[data-flow=plan][data-state=active]').waitFor();
    await page.locator('#agent-analysis[data-state=complete]').waitFor();
    assert.equal(requests,1,'Replay must not send another simulation request');
    if(process.env.SCREENSHOT_DIR){
      fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});
      await page.locator('#agent-analysis').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'travel-agent-analysis-desktop.png'),animations:'disabled'});
    }
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Travel workbench overflows mobile');
    if(process.env.SCREENSHOT_DIR){
      fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});
      await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'travel-agent-analysis-mobile.png'),fullPage:true});
    }
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.locator('#replay-analysis').click();
    await page.locator('#agent-analysis[data-state=complete]').waitFor();
    assert.equal(await page.locator('[data-flow=plan]').evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
    fail=true;
    page.on('dialog',dialog=>dialog.accept());
    await page.locator('#simulate').click();
    await page.locator('#agent-analysis[data-state=failed]').waitFor();
    assert.equal(await page.locator('[data-state=active]').count(),0);
    assert.equal(await page.locator('#analysis-progress').getAttribute('aria-valuenow'),'0');
    assert.equal(await page.locator('.result-card').count(),0);
    assert.equal(await page.locator('#replay-analysis').isVisible(),false);
    assert.equal(await page.locator('#simulate').isEnabled(),true);
    fail=false;
    await page.locator('#simulate').click();
    await page.locator('#agent-analysis[data-state=complete]').waitFor();
    await page.locator('.result-card').nth(2).waitFor();
    await page.locator('#campaign').fill('');
    await page.locator('#simulate').click();
    assert.equal(await page.locator('#agent-analysis').getAttribute('data-state'),'complete');
    assert.equal(requests,3);
    assert.deepEqual(errors,[]);
    console.log('Travel workbench: animated stages, progress, replay, reduced motion, failure, retry, results and mobile layout passed.');
  }finally{if(browser)await browser.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
