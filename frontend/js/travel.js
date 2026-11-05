const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (url, options = {}) => {
  const response = await fetch(url, {headers:{'Content-Type':'application/json'}, ...options});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `请求失败 (${response.status})`);
  return body;
};

let llmReady = false;
let currentPersonas = [];
let lastAnalysis = null;

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
  $('replay-analysis').hidden = true;
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
  if (!personas.length) { list.innerHTML = '<div class="empty">暂无画像，点击上方生成。</div>'; return; }
  list.innerHTML = personas.map(p => `
    <article class="persona-card">
      <div class="persona-top"><span class="emoji">${esc(p.emoji || '🧳')}</span><div><h3>${esc(p.name)} <span class="job-owner">${esc(p.age)}岁 · ${esc(p.city)} · ${esc(p.occupation)}</span></h3>
        <span class="tag">${esc(p.segment)}</span><span class="tag">${esc(p.jtbd?.core_job)}</span></div></div>
      <div class="persona-meta">${esc(p.role)} · ${esc(p.travel?.stage)} · ${esc(p.travel?.departure_window)} · ${esc(p.travel?.trip_length_days)} 天 / ${esc(p.travel?.party_size)} 人</div>
      <div class="persona-meta">人均预算约 ¥${Number(p.travel?.budget_per_person || 0).toLocaleString()} · ${p.travel?.booked ? '已预订' : '尚未预订'}</div>
      <p class="quote">“${esc(p.mindset?.quote)}”</p>
      <div class="details">${(p.blockers || []).slice(0,2).map(x=>`<span class="pill">顾虑：${esc(x)}</span>`).join('')}${(p.drivers || []).slice(0,2).map(x=>`<span class="pill">在意：${esc(x)}</span>`).join('')}</div>
      <div class="details">${(p.evidence_refs || []).map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</div>
    </article>`).join('');
}

async function loadPersonas() { renderPersonas(await api('/api/personas')); }

async function generate() {
  const button = $('generate');
  button.disabled = true; button.textContent = '生成中…';
  try {
    const jobId = $('job-filter').value;
    const personas = await api('/api/generate', {method:'POST', body:JSON.stringify({
      count:Math.max(1,Math.min(60,Number($('count').value)||7)),
      use_llm:Boolean($('generate-llm').checked),
      job_ids:jobId ? [jobId] : null,
    })});
    renderPersonas(personas);
  } catch (error) { notifyError(error); }
  finally { button.disabled = false; button.textContent = '生成画像'; }
}

async function simulate() {
  const button = $('simulate');
  const campaign = $('campaign').value.trim();
  if (!campaign) { notifyError(new Error('请输入旅行方案或营销话术')); return; }
  button.disabled = true; button.textContent = '分析中…';
  try {
    lastAnalysis = null;
    startAnalysisFlow();
    $('campaign-hits').replaceChildren();
    $('results').replaceChildren();
    const data = await api('/api/simulate', {method:'POST', body:JSON.stringify({
      campaign,
      use_llm:Boolean($('simulate-llm').checked),
      use_memory:Boolean($('simulate-memory').checked),
    })});
    await renderAnalysisFlow(data, campaign);
    lastAnalysis = {data, campaign};
    $('replay-analysis').hidden = false;
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
  if ($('replay-analysis')) $('replay-analysis').addEventListener('click', async () => {
    if (!lastAnalysis) return;
    const {data, campaign} = lastAnalysis;
    $('simulate').disabled = true;
    startAnalysisFlow();
    try { await renderAnalysisFlow(data, campaign); }
    finally { $('simulate').disabled = false; $('replay-analysis').hidden = false; }
  });
  if ($('reset-memory')) $('reset-memory').addEventListener('click', async () => {
    try { await api('/api/memories/reset', {method:'POST'}); alert('连续触达记忆已清除'); }
    catch (error) { alert(error.message); }
  });
  if ($('job-map') || $('job-filter')) loadJobMap().catch(notifyError);
  if ($('persona-list')) loadPersonas().catch(notifyError);
  if ($('factor-list')) loadFactors().catch(notifyError);
  if ($('add-factor')) $('add-factor').addEventListener('click',addFactor);
});
