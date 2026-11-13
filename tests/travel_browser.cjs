// Headless regression for the restored travel generation and analysis workbench.
const {chromium}=require('playwright');
const {service}=require('./browser_helpers.cjs');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
async function main(){
  const server=await service(8767,{researchAgent:true});let browser;
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
    const visiblePersonas=page.locator('.persona-card:visible');
    const overflow=page.locator('#persona-overflow');
    await page.locator('#count').fill('7');
    const generated=page.waitForResponse(r=>r.url().endsWith('/api/generate') && r.ok());
    await page.locator('#generate').click();
    const personas=await (await generated).json();
    await page.locator('#generate-hint').getByText('规则模式已生成 7 位画像。',{exact:true}).waitFor();
    const expand=page.getByText('展开其余 3 位画像',{exact:true});
    const assertVisiblePersonas=async count=>{
      const names=await visiblePersonas.locator('h3').evaluateAll(headings=>
        headings.map(heading=>heading.firstChild.textContent.trim()));
      assert.deepEqual(names,personas.slice(0,count).map(p=>p.name));
    };
    assert.equal(await page.locator('#persona-count').innerText(),'7 位');
    await assertVisiblePersonas(4);
    await expand.click();
    await assertVisiblePersonas(7);
    await page.getByText('收起其余画像',{exact:true}).click();
    await assertVisiblePersonas(4);
    await expand.click();
    await page.reload();
    await expand.waitFor();
    await assertVisiblePersonas(4);
    await expand.click();
    await page.locator('#count').fill('4');
    await page.locator('#generate').click();
    await page.locator('#generate-hint').getByText('规则模式已生成 4 位画像。',{exact:true}).waitFor();
    assert.equal(await overflow.isVisible(),false);
    assert.equal(await visiblePersonas.count(),4);
    await page.locator('#count').fill('3');
    await page.locator('#generate').click();
    await page.locator('#generate-hint').getByText('规则模式已生成 3 位画像。',{exact:true}).waitFor();
    assert.equal(await page.locator('.persona-card').count(),3);
    assert.equal(await overflow.isVisible(),false);
    const previousCards=await page.locator('.persona-card').allTextContents();
    await page.route('**/api/generate',async route=>{
      assert.deepEqual(route.request().postDataJSON(),{count:7,use_llm:true,job_ids:['J7']});
      await route.fulfill({status:422,json:{detail:'DeepSeek 第 2 位画像未通过质检：旅行自述重复。请重试生成。'}});
    });
    await page.locator('#count').fill('7');
    await page.locator('#job-filter').selectOption('J7');
    await page.locator('#generate-llm').check();
    await page.locator('#generate').click();
    await page.locator('#generate-hint').getByText(/生成未完成，已保留上次结果.*旅行自述重复/).waitFor();
    assert.deepEqual(await page.locator('.persona-card').allTextContents(),previousCards);
    assert.equal(await page.locator('#generate').isEnabled(),true);
    await page.unroute('**/api/generate');
    await page.locator('#campaign').fill('周末短途旅行方案，费用包含交通与住宿，可免费改期。');
    await page.getByText('快速规则仿真',{exact:true}).click();
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
    assert.equal(await page.locator('#replay-analysis').count(),0);
    assert.ok(!(await page.locator('#agent-analysis').innerText()).includes('重播过程'));
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
    await page.locator('#simulate').click();
    await page.locator('#agent-analysis[data-state=complete]').waitFor();
    assert.equal(await page.locator('[data-flow=plan]').evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
    fail=true;
    page.on('dialog',dialog=>dialog.accept());
    await page.locator('#simulate').click();
    await page.locator('#agent-analysis[data-state=failed]').waitFor();
    assert.equal(await page.locator('[data-state=active]').count(),0);
    assert.equal(await page.locator('#analysis-progress').getAttribute('aria-valuenow'),'0');
    assert.equal(await page.locator('.result-card').count(),0);
    assert.equal(await page.locator('#replay-analysis').count(),0);
    assert.equal(await page.locator('#simulate').isEnabled(),true);
    fail=false;
    await page.locator('#simulate').click();
    await page.locator('#agent-analysis[data-state=complete]').waitFor();
    await page.locator('.result-card').nth(2).waitFor();
    await page.locator('#campaign').fill('');
    await page.locator('#simulate').click();
    assert.equal(await page.locator('#agent-analysis').getAttribute('data-state'),'complete');
    assert.equal(requests,4);
    await page.locator('#campaign').fill('两天周末旅行方案，费用和改期条件待确认。');
    await page.locator('#agent-constraints').fill('总价不能增加');
    const researchConsole=page.locator('#research-console');
    const researchSteps=researchConsole.locator('[data-research-step]');
    const researchButton=page.locator('#run-research-agent');
    assert.equal(await researchConsole.locator('.console-inputs #research-agent-status').count(),1);
    assert.equal(await researchConsole.getAttribute('data-run-state'),'idle');
    assert.equal(await researchConsole.locator('.core-sweep').evaluate(el=>getComputedStyle(el).animationName),'none');
    await page.emulateMedia({reducedMotion:'no-preference'});
    if(process.env.SCREENSHOT_DIR){
      await page.locator('#agent-constraints').blur();
      await researchConsole.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'research-console-mobile.png')});
      await page.setViewportSize({width:1440,height:1000});
      await researchConsole.evaluate(el=>window.scrollBy(0,el.getBoundingClientRect().top-85));
      await researchConsole.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'research-console-desktop.png')});
      await page.setViewportSize({width:390,height:844});
    }
    let releaseResearch;
    const researchGate=new Promise(resolve=>releaseResearch=resolve);
    await page.route('**/api/agent/analyses',async route=>{
      await researchGate;
      await route.continue();
    });
    const submitted=page.waitForRequest(r=>r.method()==='POST' && r.url().endsWith('/api/agent/analyses'));
    await researchButton.click();
    assert.equal(await researchConsole.getAttribute('data-run-state'),'running');
    assert.equal(await researchButton.isDisabled(),true);
    assert.equal(await researchConsole.locator('.core-wave').evaluate(el=>getComputedStyle(el).animationName),'console-wave');
    assert.equal(await researchSteps.evaluateAll(steps=>steps.every(step=>step.dataset.stepState==='pending')),true);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Research console overflows mobile');
    releaseResearch();
    assert.equal((await submitted).postDataJSON().optimize,true);
    assert.equal((await submitted).postDataJSON().prefer_generated_personas,true);
    await page.getByText('分析与复测完成。',{exact:true}).waitFor();
    assert.equal(await researchConsole.getAttribute('data-run-state'),'completed');
    assert.equal(await researchSteps.evaluateAll(steps=>steps.every(step=>step.dataset.stepState==='complete')),true);
    assert.deepEqual(await page.locator('.research-comparison meter').evaluateAll(meters=>meters.map(m=>[m.value,m.max])),[[0,3],[3,3]]);
    assert.match(await page.locator('#research-agent-events').innerText(),/使用原来的 3 个画像复测/);
    assert.match(await page.locator('#research-agent-result').innerText(),/原方案 0 \/ 3，修改稿 3 \/ 3/);
    assert.match(await page.locator('#research-agent-result').innerText(),/3 个已生成的旅游意向画像/);
    const researchResult=page.locator('#research-agent-result');
    assert.match(await researchResult.locator('.research-changes').innerText(),/原方案\s+费用和改期条件待确认\s+修改稿\s+明确费用及改期条件/);
    assert.equal(await researchResult.locator('.research-draft').isVisible(),false);
    await researchResult.getByText('查看完整修改稿 · 补充条件').click();
    assert.equal(await researchResult.locator('.research-draft').isVisible(),true);
    const profileResult=researchResult.locator('.research-profile').first();
    assert.match(await profileResult.innerText(),/原方案 4\/10 → 修改稿 8\/10/);
    assert.match(await profileResult.innerText(),/我还不知道改期要付多少钱/);
    await profileResult.getByText('查看逐项依据').click();
    assert.match(await profileResult.locator('details').innerText(),/修改稿：满足/);
    const report=await page.getByRole('link',{name:'下载研究报告'}).getAttribute('href');
    assert.match(await (await page.request.get(new URL(report,page.url()).href)).text(),/同一画像集合复测/);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Research results overflow mobile');
    await page.locator('#campaign').fill('模拟工具选择失败：周末旅行，费用待确认。');
    await page.locator('#run-research-agent').click();
    await page.getByText('部分完成，请查看报告中的未完成项。',{exact:true}).waitFor();
    assert.equal(await researchConsole.getAttribute('data-run-state'),'partial');
    assert.equal(await researchSteps.evaluateAll(steps=>steps.map(step=>step.dataset.stepState).join(',')),'complete,complete,failed,pending');
    assert.equal(await page.locator('.research-comparison meter').count(),1);
    assert.match(await page.locator('#research-agent-result').innerText(),/已保留原方案分析/);
    assert.match(await page.locator('#research-agent-result').innerText(),/后续步骤未完成/);
    await page.unroute('**/api/agent/analyses');
    await page.route('**/api/agent/analyses',route=>route.fulfill({status:503,json:{detail:'研究服务暂不可用'}}));
    await researchButton.click();
    await page.getByText('研究服务暂不可用',{exact:true}).waitFor();
    assert.equal(await researchConsole.getAttribute('data-run-state'),'failed');
    assert.equal(await researchButton.isEnabled(),true);
    assert.equal(await researchConsole.locator('[aria-current=step]').count(),0);
    await page.unroute('**/api/agent/analyses');
    await page.route('**/api/agent/analyses',route=>route.fulfill({status:422,json:{detail:[
      {type:'extra_forbidden',loc:['body','prefer_generated_personas'],msg:'Extra inputs are not permitted',input:true},
    ]}}));
    await page.locator('#campaign').fill('上海出发，苏州周末两天一晚，2 人同行，人均预算 800 元，含往返高铁、一晚住宿和一个园林门票，餐饮自理。');
    await researchButton.click();
    await page.getByText('当前后端版本过旧。请重启旅游沙盘服务，刷新页面后重试。',{exact:true}).waitFor();
    assert.equal(await page.locator('#research-agent-status').isVisible(),true);
    assert.equal(await researchButton.isEnabled(),true);
    await page.unroute('**/api/agent/analyses');
    await researchButton.click();
    await page.getByText('分析与复测完成。',{exact:true}).waitFor();
    assert.equal(await researchConsole.getAttribute('data-run-state'),'completed');
    assert.deepEqual(errors,[]);
    console.log('Travel workbench: persona disclosure, rule simulation, Agent retest, execution events, report and mobile layout passed.');
  }finally{if(browser)await browser.close();server.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
