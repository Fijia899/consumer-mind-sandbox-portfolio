// Temporary single-process service for headless regression. No production writes.
const {spawn}=require('node:child_process');
const path=require('node:path');
const assert=require('node:assert/strict');
async function service(port) {
  const code=`import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'backend'))
from services import participant_store as store,participant_predictions as predictions,agent_store,persona_store,research_store
from routes import travel
def model(mode,campaign,facts,insights,context):
    return {'decision':'hesitate' if mode=='generic' else 'advance','supporting_fact_ids':[facts[0]['id']] if facts else [],'campaign_quotes':[campaign],'missing_information':['Test-only confirmation question']}
predictions.request_model=model
with tempfile.TemporaryDirectory() as temp:
    directory=Path(temp)
    store.STATE_PATH=directory/'participants.json'
    research_store.STATE_PATH=directory/'research.json'
    travel.MEMORY_PATH=directory/'travel_memories.json'
    agent_store.DB_PATH=directory/'agent.sqlite3'
    agent_store.MEDIA_DIR=directory/'media'
    store.ARCHIVE_DIR=directory/'archive'
    persona_store.PERSONAS_PATH=directory/'personas.json'
    old=directory/'personas.json'
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
