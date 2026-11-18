// Temporary single-process service for headless regression. No production writes.
const {spawn}=require('node:child_process');
const path=require('node:path');
const assert=require('node:assert/strict');
async function service(port, {researchAgent = false} = {}) {
  const code=`import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'backend'))
from services import participant_store as store,participant_predictions as predictions,agent_store,persona_store,research_store
def model(mode,campaign,facts,insights,context):
    return {'decision':'hesitate' if mode=='generic' else 'advance','supporting_fact_ids':[facts[0]['id']] if facts else [],'campaign_quotes':[campaign],'missing_information':['Test-only confirmation question']}
predictions.request_model=model
${researchAgent ? `from services import research_agent
from routes import travel
travel.llm_configured=lambda: True
def research_model(identifier,deadline,instruction,payload):
    if "选择工具" in instruction:
        if payload["remaining_ids"]:
            return {"tool":"analyze_batch","arguments":{"profile_ids":payload["remaining_ids"][:6]}}
        if payload["plan"].startswith("模拟工具选择失败"):
            raise ValueError("模型连续两次未返回合法 JSON；请重试任务")
        return {"tool":"finish" if payload["has_recommendations"] else "propose_changes","arguments":{}}
    if "逐项判断" in instruction:
        revised=payload["plan"].startswith("复测样例")
        return {"cases":[{"profile_id":p["id"],"willingness":8 if revised else 4,
            "concern":"我看到了改期条件，可以继续了解。" if revised else "我还不知道改期要付多少钱。",
            "rows":[
            {"need_id":n["id"],"status":"met" if revised else "uncovered","explanation":"浏览器隔离验证",
             "plan_quotes":[payload["plan"]] if revised else [],"factor_matches":[]} for n in p["needs"]]} for p in payload["profiles"]]}
    return {"summary":"原方案缺少需求细节","questions":["核实改期条件"],"candidates":[
        {"title":"补充条件","plan":"复测样例：明确费用及改期条件。","tradeoff":"需确认服务成本",
         "changes":[{"before":"费用和改期条件待确认" if "费用和改期条件待确认" in payload["plan"] else "",
                     "after":"明确费用及改期条件","reason":"回应改期费用顾虑"}]}]}
research_agent.model_json=research_model` : ''}
with tempfile.TemporaryDirectory() as temp:
    directory=Path(temp)
    from routes import travel
    travel.MEMORY_PATH=directory/'travel_memories.json'
    store.STATE_PATH=directory/'participants.json'
    research_store.STATE_PATH=directory/'research.json'
    agent_store.DB_PATH=directory/'agent.sqlite3'
    agent_store.MEDIA_DIR=directory/'media'
    store.ARCHIVE_DIR=directory/'archive'
    persona_store.PERSONAS_PATH=directory/'personas.json'
    old=directory/'legacy_personas.json'
    old.write_text(json.dumps([{'id':'test-archive','name':'Browser test archive'}]),encoding='utf-8')
    store.LEGACY_PATHS=[old]
    import uvicorn
    uvicorn.run('main:app',host='127.0.0.1',port=${port},log_level='error')`;
  const server=spawn(process.env.PYTHON||'python',['-c',code],{cwd:path.resolve(__dirname,'..'),windowsHide:true,stdio:'pipe'});
  let errors='';server.stderr.on('data',x=>errors+=x);server.stdout.resume();
  try {
    for(let i=0;i<100;i++){
      if(server.exitCode!==null)throw new Error(errors);
      try{if((await fetch(`http://127.0.0.1:${port}/api/health`)).ok)return server;}catch{}
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    assert.fail('Server did not start: '+errors);
  }catch(error){server.kill();throw error;}
}
module.exports={service};
