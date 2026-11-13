const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (url, options = {}) => {
  const response = await fetch(url, {headers:{'Content-Type':'application/json'}, ...options});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const {detail} = body;
    if (Array.isArray(detail)) {
      if (url === '/api/agent/analyses' && detail.some(issue =>
        issue?.type === 'extra_forbidden' && issue.loc?.at(-1) === 'prefer_generated_personas')) {
        throw new Error('当前后端版本过旧。请重启旅游沙盘服务，刷新页面后重试。');
      }
      const messages = detail.map(issue => issue?.msg).filter(message => typeof message === 'string');
      if (messages.length) throw new Error(messages.join('；'));
    }
    throw new Error(typeof detail === 'string' && detail ? detail : `请求失败 (${response.status})`);
  }
  return body;
};

let llmReady = false;
let currentPersonas = [];

const flowPause = () => new Promise(resolve => setTimeout(resolve,
  window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 520));

function setFlowProgress(completed, message) {
  $('analysis-progress').setAttribute('aria-valuenow', String(completed));
  $('analysis-progress').querySelector('span').style.width = `${completed * 25}%`;
  $('analysis-status').textContent = message;
}

function startAnalysisFlow() {
  const flow = $('agent-analysis');
  flow.hidden = false;
  flow.dataset.state = 'running';
  $('agent-analysis-count').textContent = '分析中';
  flow.querySelectorAll('[data-flow]').forEach((item, index) => {
    item.dataset.state = index === 0 ? 'active' : 'pending';
    item.querySelector('p').textContent = index === 0 ? '正在提交旅行方案，等待分析结果…' : '等待分析';
    if (index === 0) item.setAttribute('aria-current', 'step');
    else item.removeAttribute('aria-current');
  });
  setFlowProgress(0, '正在分析旅行方案…');
}

function notifyError(error) { alert(error.message || String(error)); }

async function loadConfig() {
  const state = await api('/api/config');
  llmReady = state.llm_configured;
  const status = $('api-status');
  if (status) {
    status.textContent = llmReady ? `DeepSeek 已配置 · ${state.model}` : '规则模式可用 · DeepSeek 待配置';
    status.classList.toggle('ready', llmReady);
  }
  for (const id of ['generate-llm','simulate-llm']) {
    const input = $(id);
    if (input) input.disabled = !llmReady;
  }
  const hint = $('generate-hint');
  if (hint && !llmReady) hint.textContent = '如需复用漫创配置，请设置 MANCHUANG_ENV_FILE 指向其 .env；API Key 不需要复制进本项目。';
}

function renderPersonas(personas) {
  currentPersonas = personas;
  const list = $('persona-list');
  if (!list) return;
  $('persona-count').textContent = `${personas.length} 位`;
  const previewLimit = 4;
  const overflow = $('persona-overflow');
  overflow.open = false;
  overflow.hidden = personas.length <= previewLimit;
  $('persona-extra-list').replaceChildren();
  if (!personas.length) { list.innerHTML = '<div class="empty">暂无画像，点击上方生成。</div>'; return; }
  const cards = personas.map(p => `
    <article class="persona-card">
      <div class="persona-top"><span class="emoji">${esc(p.emoji || '🧳')}</span><div><h3>${esc(p.name)} <span class="job-owner">${esc(p.age)}岁 · ${esc(p.city)} · ${esc(p.occupation)}</span></h3>
        <span class="tag">${esc(p.segment)}</span><span class="tag">${esc(p.jtbd?.core_job)}</span></div></div>
      <div class="persona-meta">${esc(p.role)} · ${esc(p.travel?.stage)} · ${esc(p.travel?.departure_window)} · ${esc(p.travel?.trip_length_days)} 天 / ${esc(p.travel?.party_size)} 人</div>
      <div class="persona-meta">人均预算约 ¥${Number(p.travel?.budget_per_person || 0).toLocaleString()} · ${p.travel?.booked ? '已预订' : '尚未预订'}</div>
      <p class="quote">“${esc(p.mindset?.quote)}”</p>
      <div class="details">${(p.blockers || []).slice(0,2).map(x=>`<span class="pill">顾虑：${esc(x)}</span>`).join('')}${(p.drivers || []).slice(0,2).map(x=>`<span class="pill">在意：${esc(x)}</span>`).join('')}</div>
      <div class="details">${(p.evidence_refs || []).map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</div>
    </article>`);
  list.innerHTML = cards.slice(0, previewLimit).join('');
  if (!overflow.hidden) {
    $('persona-expand-label').textContent = `展开其余 ${personas.length - previewLimit} 位画像`;
    $('persona-extra-list').innerHTML = cards.slice(previewLimit).join('');
  }
}

async function loadPersonas() { renderPersonas(await api('/api/personas')); }

async function generate() {
  const button = $('generate');
  const hint = $('generate-hint');
  const useLlm = $('generate-llm').checked;
  button.disabled = true; button.textContent = '生成中…';
  hint.textContent = useLlm ? 'DeepSeek 正在生成画像并逐一检查差异…' : '正在生成规则画像…';
  try {
    const jobId = $('job-filter').value;
    const personas = await api('/api/generate', {method:'POST', body:JSON.stringify({
      count:Math.max(1,Math.min(60,Number($('count').value)||7)),
      use_llm:useLlm,
      job_ids:jobId ? [jobId] : null,
    })});
    renderPersonas(personas);
    hint.textContent = useLlm
      ? `DeepSeek 已生成并通过质检：${personas.length} 位画像。`
      : `规则模式已生成 ${personas.length} 位画像。`;
  } catch (error) {
    hint.textContent = `生成未完成，已保留上次结果。${error.message || String(error)}`;
  }
  finally { button.disabled = false; button.textContent = '生成画像'; }
}

async function simulate() {
  const button = $('simulate');
  const campaign = $('campaign').value.trim();
  if (!campaign) { notifyError(new Error('请输入旅行方案或营销话术')); return; }
  button.disabled = true; button.textContent = '分析中…';
  try {
    startAnalysisFlow();
    $('campaign-hits').replaceChildren();
    $('results').replaceChildren();
    const data = await api('/api/simulate', {method:'POST', body:JSON.stringify({
      campaign,
      use_llm:Boolean($('simulate-llm').checked),
      use_memory:Boolean($('simulate-memory').checked),
    })});
    await renderAnalysisFlow(data, campaign);
    $('campaign-hits').innerHTML = `<span>识别到的关注点</span>${data.campaign_hits.map(x=>`<span>${esc(x)}</span>`).join('') || '<span>暂未命中已定义的关键词</span>'}`;
    $('results').innerHTML = data.results.map(r => `
      <article class="result-card"><h3>${esc(r.persona_name)}<span class="decision ${esc(r.decision)}">${({advance:'愿意继续',hesitate:'仍需确认',reject:'不接受',na:'无关'})[r.decision] || esc(r.decision)}</span></h3>
        <p>${esc(r.reaction)}</p><p class="hint">${esc(r.reasoning || '')}</p>
        <div class="score"><span style="width:${Math.max(0,Math.min(100,Number(r.willingness || 0)*10))}%"></span></div>
        <div class="details">${(r.outcome_improved || []).map(x=>`<span class="pill">已回应 ${esc(x)}</span>`).join('')}${(r.unresolved_outcomes || []).slice(0,3).map(x=>`<span class="pill">待解决 ${esc(x)}</span>`).join('')}</div>
      </article>`).join('');
  } catch (error) {
    const flow = $('agent-analysis');
    if (flow && !flow.hidden) {
      flow.dataset.state = 'failed';
      $('agent-analysis-count').textContent = '分析未完成';
      $('analysis-status').textContent = '分析中断，请重新运行测试';
      flow.querySelectorAll('[data-state="active"]').forEach(item => {
        item.dataset.state = 'failed';
        item.removeAttribute('aria-current');
        item.querySelector('p').textContent = '请求未完成，请重试。';
      });
    }
    notifyError(error);
  }
  finally { button.disabled = false; button.textContent = '运行测试'; }
}

async function renderAnalysisFlow(data, campaign) {
  const flow = $('agent-analysis');
  const count = data.results.length;
  const total = Object.values(data.summary || {}).reduce((sum, value) => sum + Number(value || 0), 0);
  const hits = data.campaign_hits || [];
  const outcomes = data.results.reduce((sum, row) => sum + (row.outcome_improved || []).length + (row.unresolved_outcomes || []).length, 0);
  const summary = data.summary || {};
  const labels = {advance:'愿意继续', hesitate:'仍需确认', reject:'不接受', na:'无关'};
  const finalSummary = Object.entries(labels).map(([key,label]) => `${label} ${Number(summary[key] || 0)}`).join(' · ');
  const stages = {
    plan: `读取方案文本 ${campaign.length} 字，选择 ${count} 个旅游意向画像。`,
    factors: hits.length ? `命中 ${hits.length} 项决策维度：${hits.join('、')}。` : '未命中已配置的决策维度关键词。',
    personas: `完成 ${count} 个人物分析，共检查 ${outcomes} 项任务结果。`,
    summary: `汇总 ${total} 条分类结果：${finalSummary}。`,
  };
  const items = [...flow.querySelectorAll('[data-flow]')];
  for (const [index, item] of items.entries()) {
    item.dataset.state = 'active';
    item.setAttribute('aria-current', 'step');
    item.querySelector('p').textContent = stages[item.dataset.flow];
    setFlowProgress(index, `结果展示 ${index + 1} / 4 · ${item.querySelector('strong').textContent}`);
    await flowPause();
    item.dataset.state = 'complete';
    item.removeAttribute('aria-current');
  }
  setFlowProgress(4, '分析完成 · 结果已就绪');
  flow.dataset.state = 'complete';
  $('agent-analysis-count').textContent = `${count} 个画像 · ${hits.length} 个维度`;
}

const researchStatuses = {met:'满足', partial:'部分满足', conflict:'冲突', uncovered:'未覆盖', unknown:'无法判断', failed:'分析失败'};

const researchStepStates = {pending:'待执行', active:'进行中', complete:'已完成', partial:'部分完成', failed:'未完成'};

function setResearchStep(step, state) {
  step.dataset.stepState = state;
  step.querySelector('small').textContent = researchStepStates[state];
  if (state === 'active') step.setAttribute('aria-current', 'step');
  else step.removeAttribute('aria-current');
}

function updateResearchFlow(steps, event) {
  const {tool, status} = event;
  if (tool === 'select_profiles' && status === 'completed') {
    setResearchStep(steps.profiles, 'complete');
  }
  if (['analyze_batch', 'find_gaps'].includes(tool) && status === 'running' &&
      steps.baseline.dataset.stepState !== 'complete' && steps.draft.dataset.stepState !== 'active') {
    setResearchStep(steps.baseline, 'active');
  }
  if (tool === 'propose_changes' && status === 'running') {
    if (steps.baseline.dataset.stepState === 'active') setResearchStep(steps.baseline, 'pending');
    setResearchStep(steps.draft, 'active');
  }
  if (tool === 'propose_changes' && status === 'rejected') {
    setResearchStep(steps.draft, 'pending');
  }
  if (tool === 'propose_changes' && status === 'completed') {
    setResearchStep(steps.baseline, 'complete');
    setResearchStep(steps.draft, 'complete');
  }
  if (tool === 'retest_candidate') {
    const state = {running:'active', progress:'active', completed:'complete', partial:'partial', failed:'failed'}[status];
    if (state) setResearchStep(steps.retest, state);
  }
}

function renderResearchResult(run, url) {
  const {result, snapshot} = run;
  const {metrics, retest} = result;
  const draft = retest?.candidate;
  const recommendations = result.recommendations || {summary:'已保留原方案分析。', questions:[]};
  const baseline = new Map(result.cases.map(item => [item.profile_id, item]));
  const revised = new Map((retest?.cases || []).map(item => [item.profile_id, item]));
  const coverage = (label, stats) => `<div><span>${label}</span>
    <meter min="0" max="${Math.max(1, stats.total)}" value="${stats.counts.met}" aria-label="${label}全部需求满足的画像"></meter>
    <strong>${stats.counts.met} / ${stats.total}</strong></div>`;
  function finding(row) {
    if (!row) return '未取得有效结果';
    const quotes = row.plan_quotes.length ? ` · 依据：${row.plan_quotes.join('；')}` : '';
    return esc(`${researchStatuses[row.status]} · ${row.explanation}${quotes}`);
  }
  const score = item => item?.willingness != null ? `${item.willingness}/10` :
    item?.status === 'failed' ? '分析失败' : '暂无评分';
  const profiles = snapshot.profiles.map(profile => {
    const original = baseline.get(profile.id);
    const updated = revised.get(profile.id);
    const before = new Map((original?.rows || []).map(row => [row.need_id, row]));
    const after = new Map((updated?.rows || []).map(row => [row.need_id, row]));
    return `<section class="research-profile">
      <h5>${esc(profile.label)}</h5>
      <p><strong>原方案 ${score(original)}${draft ? ` → 修改稿 ${score(updated)}` : ''}</strong></p>
      <p>我的顾虑 · 原方案${original?.concern ? `「${esc(original.concern)}」` : ' · 暂无记录'}</p>
      ${updated?.concern ? `<p>修改稿反馈「${esc(updated.concern)}」</p>` : ''}
      <details><summary>查看逐项依据</summary>
      <p class="hint">需求覆盖 · 原方案 ${researchStatuses[original?.status] || '暂无结果'}${draft ?
        ` → 修改稿 ${researchStatuses[updated?.status] || '暂无结果'}` : ''}</p><ul>${profile.needs.map(need =>
      `<li><strong>${esc(need.label)}</strong><div>原方案：${finding(before.get(need.id))}</div>
       ${draft ? `<div>修改稿：${finding(after.get(need.id))}</div>` : ''}</li>`).join('')}</ul></details></section>`;
  }).join('');
  $('research-agent-result').innerHTML = `<article class="evidence-card">
    <h3>方案分析结果</h3><p>${esc(recommendations.summary)}</p>
    <p>全部需求都满足的画像：原方案 ${metrics.counts.met} / ${metrics.total}${retest?.metrics ?
      `，修改稿 ${retest.metrics.counts.met} / ${retest.metrics.total}` : ''}。</p>
    <div class="research-comparison">${coverage('原方案', metrics)}${retest?.metrics ? coverage('修改稿', retest.metrics) : ''}</div>
    ${draft ? `<h4>改了什么</h4>
    ${draft.changes?.length ? `<ol class="research-changes">${draft.changes.map(change => `<li>
      <div><strong>原方案</strong> ${change.before ? esc(change.before) : '无对应内容'}</div>
      <div><strong>修改稿</strong> ${change.after ? esc(change.after) : '删除此项'}</div>
      <div class="hint">${esc(change.reason)}</div></li>`).join('')}</ol>` : '<p>本次报告没有记录逐项改动。</p>'}
    <details><summary>查看完整修改稿 · ${esc(draft.title)}</summary><blockquote class="research-draft">${esc(draft.plan)}</blockquote>
    <p>取舍：${esc(draft.tradeoff)}</p></details>` : ''}
    ${run.error || retest?.error ? `<p>后续步骤未完成：${esc(run.error || retest.error)}</p>` : ''}
    ${recommendations.questions.length ? `<h4>待核实</h4><ul>${recommendations.questions.map(question => `<li>${esc(question)}</li>`).join('')}</ul>` : ''}
    <h4>画像评分与顾虑</h4>
    <p class="hint">评分为画像模拟的出行推进意愿（1–10 分）。第一人称反馈为模拟表述。${esc(snapshot.cohort_notice)}。</p>
    ${profiles}
    <a class="source-link" href="${url}/report">下载研究报告</a>
  </article>`;
}

async function runResearchAgent() {
  const button = $('run-research-agent');
  const status = $('research-agent-status');
  const plan = $('campaign').value.trim();
  if (plan.length < 5) { status.textContent = '请输入至少 5 个字的旅游方案。'; return; }
  const consolePanel = $('research-console');
  const badge = $('research-console-badge');
  const steps = Object.fromEntries([...consolePanel.querySelectorAll('[data-research-step]')]
    .map(step => [step.dataset.researchStep, step]));
  button.disabled = true;
  consolePanel.dataset.runState = 'running';
  badge.textContent = '正在启动';
  Object.values(steps).forEach(step => setResearchStep(step, 'pending'));
  status.textContent = '正在提交研究任务…';
  const events = $('research-agent-events');
  events.replaceChildren();
  $('research-agent-log').hidden = true;
  $('research-agent-result').replaceChildren();
  try {
    if (!llmReady) throw new Error('请先配置 DeepSeek，再运行研究 Agent。');
    const run = await api('/api/agent/analyses', {method:'POST', body:JSON.stringify({
      mode:'general', prefer_generated_personas:true, cohort_size:6, optimize:true, plan, constraints:$('agent-constraints').value.trim(),
    })});
    const url = `/api/agent/runs/${encodeURIComponent(run.id)}`;
    let cursor = 0;
    $('research-agent-log').hidden = false;
    while (true) {
      const update = await api(`${url}/events?after=${cursor}`);
      for (const event of update.events) {
        updateResearchFlow(steps, event);
        const item = document.createElement('li');
        item.textContent = event.summary;
        events.append(item);
        cursor = event.seq;
      }
      if (!['queued', 'running'].includes(update.status)) {
        const detail = await api(url);
        if (!['completed', 'partial'].includes(detail.status)) throw new Error(detail.error || '研究任务未完成。');
        renderResearchResult(detail, url);
        consolePanel.dataset.runState = detail.status;
        badge.textContent = detail.status === 'partial' ? '部分完成' : '已完成';
        const {metrics, recommendations, retest} = detail.result;
        setResearchStep(steps.baseline, metrics.analyzed === metrics.total ? 'complete' : 'partial');
        setResearchStep(steps.draft, recommendations ? 'complete' : 'failed');
        if (steps.retest.dataset.stepState === 'active') setResearchStep(steps.retest, retest ? 'partial' : 'failed');
        status.textContent = detail.status === 'partial' ? '部分完成，请查看报告中的未完成项。' : '分析与复测完成。';
        return;
      }
      badge.textContent = update.status === 'queued' ? '排队中' : '运行中';
      const active = consolePanel.querySelector('[aria-current="step"] strong');
      const message = update.status === 'queued' ? '等待执行…' :
        active ? `正在执行 · ${active.textContent}` : '等待 Agent 返回下一步…';
      if (status.textContent !== message) status.textContent = message;
      await new Promise(resolve => setTimeout(resolve, 800));
    }
  } catch (error) {
    consolePanel.dataset.runState = 'failed';
    badge.textContent = '未完成';
    Object.values(steps).filter(step => step.dataset.stepState === 'active')
      .forEach(step => setResearchStep(step, 'failed'));
    status.textContent = error.message || '暂时无法读取研究结果。';
  } finally {
    button.disabled = false;
  }
}

async function loadJobMap() {
  const data = await api('/api/jobs');
  const filter = $('job-filter');
  if (filter) filter.innerHTML += data.jobs.map(j=>`<option value="${esc(j.id)}">${esc(j.id)} · ${esc(j.name)}</option>`).join('');
  const map = $('job-map');
  if (!map) return;
  map.innerHTML = data.job_trees.map(job => `
    <article class="job-card"><div class="job-heading"><div><span class="job-id">${esc(job.id)} · ${esc(job.category)}</span><h2>${esc(job.name)}</h2></div><span class="job-owner">${esc((job.job_owners || []).join(' / '))}</span></div>
      <p class="job-statement">${esc(job.statement)}</p>
      ${(job.stages || []).map(stage=>`<div><div class="stage">${esc(stage.name)}</div>${stage.steps.map(s=>`<span class="step" title="${esc(s.id)}">${esc(s.name)}</span>`).join('')}</div>`).join('')}
      <div class="details">${(job.outcome_ids || []).map(id=>`<span class="pill">${esc(id)}</span>`).join('')}</div>
    </article>`).join('');
}

async function loadFactors() {
  const db = await api('/api/factors');
  const list = $('factor-list');
  if (!list) return;
  const enabled = db.factors.filter(f=>f.enabled).length;
  $('factor-count').textContent = `${db.factors.length} 项 · ${enabled} 项启用`;
  const groups = Object.groupBy ? Object.groupBy(db.factors, f=>f.group) : db.factors.reduce((o,f)=>((o[f.group] ||= []).push(f),o),{});
  list.innerHTML = Object.entries(groups).map(([group, rows])=>`<section><div class="factor-group">${esc(group)} · ${group === 'A' ? '出行触发' : '决策顾虑'}</div>${rows.map(f=>`
    <div class="factor-row"><div class="factor-code">${esc(f.id)}</div><div><div class="factor-name">${esc(f.name)}</div><div class="factor-definition">${esc(f.definition)}</div><div class="factor-tags">关联任务 ${(f.job_ids || []).map(esc).join(' / ')} · ${esc(f.source)}</div><div class="weight">权重 ${esc(f.weight)}/10</div></div><label class="factor-toggle"><input type="checkbox" data-id="${esc(f.id)}" ${f.enabled?'checked':''}>启用</label></div>`).join('')}</section>`).join('');
  list.querySelectorAll('[data-id]').forEach(input=>input.addEventListener('change', async()=>{
    try { await api(`/api/factors/${encodeURIComponent(input.dataset.id)}`, {method:'PUT',body:JSON.stringify({enabled:input.checked})}); await loadFactors(); }
    catch(error) { input.checked=!input.checked; notifyError(error); }
  }));
}

async function addFactor() {
  const keywords = $('f-keywords').value.split(/[,，]/).map(x=>x.trim()).filter(Boolean);
  try {
    await api('/api/factors',{method:'POST',body:JSON.stringify({id:$('f-id').value.trim(),group:$('f-group').value,name:$('f-name').value.trim(),weight:Number($('f-weight').value)||5,definition:$('f-definition').value.trim(),keywords,enabled:true,source:'沙盘假设，待验证'})});
    for (const id of ['f-id','f-name','f-definition','f-keywords']) $(id).value='';
    await loadFactors();
  } catch(error) { notifyError(error); }
}

document.addEventListener('DOMContentLoaded', async()=>{
  try { await loadConfig(); } catch(error) { console.error(error); }
  if ($('generate')) $('generate').addEventListener('click',generate);
  if ($('simulate')) $('simulate').addEventListener('click',simulate);
  if ($('run-research-agent')) $('run-research-agent').addEventListener('click',runResearchAgent);
  if ($('reset-memory')) $('reset-memory').addEventListener('click', async () => {
    try { await api('/api/memories/reset', {method:'POST'}); alert('连续触达记忆已清除'); }
    catch (error) { alert(error.message); }
  });
  if ($('job-map') || $('job-filter')) loadJobMap().catch(notifyError);
  if ($('persona-list')) loadPersonas().catch(notifyError);
  if ($('factor-list')) loadFactors().catch(notifyError);
  if ($('add-factor')) $('add-factor').addEventListener('click',addFactor);
});
