import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const root = "D:/Xiaofeizheshapan";
const buildDir = path.join(root, ".codex-build-mind-sandbox-bp");
const outDir = path.join(root, "outputs");
const draft = path.join(buildDir, "consumer-mind-sandbox-bp-draft.pptx");
const out = path.join(outDir, "消费者心智沙盘_BP.pptx");
const skillDir = "C:/Users/fkxlucky/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const { resolvePresentationFont } = await import(pathToFileURL(path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);
await fs.mkdir(buildDir, { recursive: true }); await fs.mkdir(outDir, { recursive: true });
const font = resolvePresentationFont({ fontFamily: "Aptos" });
const C = { ink:"#17252D", navy:"#173B4D", teal:"#2C8A87", mint:"#E8F4F1", sand:"#F5F1EA", coral:"#E47765", line:"#D3DFDE", muted:"#64747B", white:"#FFFFFF" };
const deck = Presentation.create({ slideSize:{width:1280,height:720} });
function shape(s,x,y,w,h,fill="none",line="none",round=false){return s.shapes.add({geometry:round?"roundRect":"rect",position:{left:x,top:y,width:w,height:h},fill,line:{fill:line,width:line==="none"?0:1}})}
function tx(s,v,x,y,w,h,fs=20,color=C.ink,o={}){const t=s.shapes.add({geometry:"textbox",position:{left:x,top:y,width:w,height:h},fill:"none",line:{fill:"none",width:0}});t.text=v;t.text.style={typeface:font,fontSize:fs,color,bold:!!o.bold,italic:!!o.italic,autoFit:"shrink"};if(o.align)t.text.paragraphFormat={alignment:o.align};return t}
function head(s,k,h,sub=""){tx(s,k.toUpperCase(),70,48,500,22,13,C.teal,{bold:true});tx(s,h,70,78,1120,55,34,C.navy,{bold:true});if(sub)tx(s,sub,70,140,1080,28,16,C.muted)}
function foot(s,n){shape(s,70,681,1140,1,C.line);tx(s,"消费者心智沙盘｜独立研究与策略工具",70,690,500,16,10,C.muted);tx(s,String(n).padStart(2,"0"),1160,690,50,16,10,C.muted,{align:"right"})}
function note(s,v){s.speakerNotes.textFrame.setText(v)}
function item(s,x,y,w,title,body,fill=C.sand){shape(s,x,y,w,100,fill,"none",true);tx(s,title,x+18,y+18,w-36,24,17,C.navy,{bold:true});tx(s,body,x+18,y+52,w-36,36,14,C.ink)}

// 1
{const s=deck.slides.add();s.background.fill=C.sand;shape(s,70,70,12,125,C.teal);tx(s,"CONSUMER MIND SANDBOX",110,78,700,35,17,C.teal,{bold:true});tx(s,"把消费者研究\n变成可运行的决策工具",110,175,850,140,47,C.navy,{bold:true});tx(s,"面向产品、内容与增长团队的心智模拟平台\n创业项目 BP｜独立产品方案",114,360,720,65,21,C.ink);shape(s,900,175,240,240,C.mint,"none",true);tx(s,"输入一个方案",930,220,180,32,20,C.navy,{bold:true,align:"center"});tx(s,"看到不同用户\n如何被触发",930,290,180,62,25,C.teal,{bold:true,align:"center"});tx(s,"再决定先验证什么",930,380,180,25,14,C.muted,{align:"center"});tx(s,"2026.09",110,610,200,24,14,C.muted);note(s,"本 BP 的主体是消费者心智沙盘，而不是某一个垂直 App。抚心只是可接入沙盘的示例应用。")}
// 2
{const s=deck.slides.add();s.background.fill=C.white;head(s,"01｜问题","用户研究有资料，团队却难以持续使用","研究资产散落在访谈、文档和会议记录里，方案仍靠经验反复试错");const a=[["资料分散","访谈、问卷、客服反馈各自保存"],["用户被扁平化","只看年龄、城市，忽略动机和阻力"],["方案难比较","文案、功能、价格缺少统一测试场"],["反馈难复用","一次研究结束后，结论很难进入下一次决策"]];a.forEach((r,i)=>item(s,70+(i%2)*580,220+Math.floor(i/2)*140,520,r[0],r[1],i===2?C.mint:C.sand));shape(s,70,545,1140,70,C.navy,"none",true);tx(s,"机会：把“消费者为什么这样反应”变成团队可以反复运行的模型。",105,566,1070,28,21,C.white,{bold:true,align:"center"});foot(s,2);note(s,"问题陈述是产品假设，需通过目标客户访谈进一步确认。")}
// 3
{const s=deck.slides.add();s.background.fill=C.sand;head(s,"02｜客户","沙盘服务需要决策的团队","第一批客户不是所有企业，而是持续测试用户反应的产品和内容团队");const rows=[["产品团队","功能、流程、定价的用户反应","减少错误开发"],["内容与增长团队","广告、推送、落地页的分化反应","提高测试效率"],["用户研究团队","用户洞察结构化与复用","让洞察进入决策"],["专业服务机构","为客户提供策略预演","增加交付深度"]];rows.forEach((r,i)=>{const y=215+i*88;shape(s,70,y,1140,68,i===1?C.navy:C.white,"none",true);tx(s,r[0],95,y+20,210,24,17,i===1?C.white:C.navy,{bold:true});tx(s,r[1],340,y+20,470,24,16,i===1?C.mint:C.ink);tx(s,r[2],865,y+20,290,24,16,i===1?C.mint:C.ink,{bold:true})});tx(s,"抚心是第一个垂直应用案例，用来验证情感健康场景。",70,590,900,25,14,C.muted,{italic:true});foot(s,3)}
// 4
{const s=deck.slides.add();s.background.fill=C.white;head(s,"03｜产品","一套可运行的消费者心智模型","将消费者洞察转为维度、Persona、场景和可比较的测试结果");const blocks=[["维度库","记录影响决策的动机、痛点、顾虑与触发词"],["Persona","组合维度，生成具有矛盾和差异的虚拟用户"],["Scenario","定义用户处于什么情境，正在完成什么任务"],["测试引擎","输入文案、功能或方案，输出反应与风险"],["校准闭环","用真实反馈修正模型和信心等级"]];blocks.forEach((r,i)=>{const x=70+(i%3)*380,y=i<3?220:410;shape(s,x,y,320,125,i===2?C.navy:C.mint,"none",true);tx(s,r[0],x+20,y+22,280,25,18,i===2?C.white:C.navy,{bold:true,align:"center"});tx(s,r[1],x+28,y+64,264,45,14,i===2?C.mint:C.ink,{align:"center"});});tx(s,"可替换应用：抚心、睡眠、教育、消费品、医疗服务等",70,600,1100,25,16,C.teal,{bold:true,align:"center"});foot(s,4)}
// 5
{const s=deck.slides.add();s.background.fill=C.sand;head(s,"04｜工作方式","同一方案，不同心智给出不同反应","沙盘的价值在于暴露分化、形成假设，而不是承诺预测每个真实用户");shape(s,70,220,480,300,C.white,"none",true);tx(s,"输入",100,250,150,25,15,C.teal,{bold:true});tx(s,"“今晚想联系前任吗？\n先陪自己撑过 10 分钟。”",100,300,390,80,27,C.navy,{bold:true});tx(s,"一条推送，也可以换成产品功能、价格或活动方案",100,430,390,40,14,C.muted);const out=[["夜间脆弱型","愿意打开","即时缓解"],["等待复合型","犹豫","害怕放弃希望"],["抗拒鸡汤型","先看再判断","需要具体行动"]];out.forEach((r,i)=>{const y=220+i*100;shape(s,650,y,500,78,i===1?C.navy:C.mint,"none",true);tx(s,r[0],675,y+16,180,22,16,i===1?C.white:C.navy,{bold:true});tx(s,r[1],875,y+16,120,22,16,i===1?C.mint:C.ink,{bold:true});tx(s,r[2],1010,y+16,110,35,14,i===1?C.mint:C.muted);});foot(s,5);note(s,"示例使用抚心场景，仅用于说明沙盘机制，不构成心理治疗或效果承诺。")}
// 6
{const s=deck.slides.add();s.background.fill=C.white;head(s,"05｜方法","从洞察到可执行的测试结果","每个结论保留来源、信心和待验证状态");const flow=[["用户反馈","访谈、问卷、客服反馈"],["结构化","提炼触发、动机、阻力"],["模拟","生成多个 Persona 并运行方案"],["验证","真实用户体验与行为数据"],["更新","修正维度、规则和信心"]];flow.forEach((r,i)=>{const x=65+i*235;shape(s,x,260,190,145,i===2?C.navy:C.mint,"none",true);tx(s,r[0],x+15,285,160,25,17,i===2?C.white:C.navy,{bold:true,align:"center"});tx(s,r[1],x+15,335,160,45,14,i===2?C.mint:C.ink,{align:"center"});if(i<4)tx(s,"→",x+195,315,35,30,23,C.coral,{bold:true,align:"center"})});shape(s,200,500,880,70,C.sand,"none",true);tx(s,"输出不是“答案”，而是下一轮验证的优先级",235,522,810,28,21,C.navy,{bold:true,align:"center"});foot(s,6)}
// 7
{const s=deck.slides.add();s.background.fill=C.sand;head(s,"06｜产品形态","一个团队可以反复使用的测试工作台","第一版围绕“方案输入—用户反应—研究结论”建立最小闭环");const tabs=[["建立研究资产","上传或录入维度、访谈摘要、用户原话"],["生成用户群体","按数量和约束生成 Persona"],["测试方案","输入广告、功能、价格或流程"],["查看结果","分群反馈、触发维度、风险与建议"]];tabs.forEach((r,i)=>{const x=70+(i%2)*580,y=220+Math.floor(i/2)*145;shape(s,x,y,520,110,i===3?C.navy:C.white,"none",true);tx(s,String(i+1),x+25,y+25,35,30,25,i===3?C.coral:C.teal,{bold:true});tx(s,r[0],x+85,y+22,380,25,18,i===3?C.white:C.navy,{bold:true});tx(s,r[1],x+85,y+60,390,28,14,i===3?C.mint:C.ink)});tx(s,"支持规则模式离线运行，LLM 只提升表达和生成质量。",70,595,900,25,16,C.teal,{bold:true});foot(s,7)}
// 8
{const s=deck.slides.add();s.background.fill=C.white;head(s,"07｜验证","先卖“研究效率”，再证明模型价值","价值验证分两条线：客户是否愿意使用，模拟是否能帮助客户做出更好决策");item(s,70,220,520,"客户价值验证","访谈 10 个产品/内容/研究团队\n确认他们现在如何测试用户反应、成本在哪里",C.mint);item(s,70,355,520,"产品使用验证","让 3–5 个团队用同一组方案完成测试\n记录是否节省研究准备时间、是否产生新假设",C.sand);item(s,690,220,520,"模型质量验证","邀请领域专家和真实用户审核 Persona、场景和反应\n所有输出标注信心等级",C.sand);item(s,690,355,520,"行为结果验证","比较沙盘判断与后续访谈、原型测试或 A/B 结果\n持续修正维度库和规则",C.mint);foot(s,8)}
// 9
{const s=deck.slides.add();s.background.fill=C.sand;head(s,"08｜商业模式","从垂直案例切入，扩展为通用产品基础设施","抚心帮助验证第一套数据和方法，沙盘产品服务更多需要用户洞察的团队");const cols=[["个人/小团队版","按月订阅\n基础 Persona 与方案测试"],["专业团队版","团队订阅\n资料管理、版本和评估集"],["企业/机构版","项目制或年度合同\n私有数据、权限与定制"],["专业服务生态","咨询公司、研究机构\n用沙盘提升交付能力"]];cols.forEach((r,i)=>{const x=70+i*285;shape(s,x,240,235,210,i===1?C.navy:C.white,"none",true);tx(s,r[0],x+18,270,199,35,17,i===1?C.white:C.navy,{bold:true,align:"center"});tx(s,r[1],x+25,340,185,65,15,i===1?C.mint:C.ink,{align:"center"})});shape(s,180,520,920,65,C.navy,"none",true);tx(s,"壁垒来自：结构化研究资产 + 可追溯 Persona + 持续校准的评估数据",210,541,860,25,19,C.white,{bold:true,align:"center"});foot(s,9);note(s,"商业模式、客户付费和壁垒均为待验证假设，未使用虚构市场规模或收入数据。")}
// 10
{const s=deck.slides.add();s.background.fill=C.navy;tx(s,"09｜路线图",70,55,400,24,14,C.mint,{bold:true});tx(s,"先做一个垂直案例，证明沙盘能改变决策",70,92,1120,55,36,C.white,{bold:true});const road=[["阶段 1","抚心案例\n10–15 个维度\n5–10 个 Persona"],["阶段 2","3–5 个团队\n测试文案与功能\n建立评估集"],["阶段 3","通用工作台\n支持多行业维度库\n团队协作与版本"],["阶段 4","产品基础设施\n连接真实行为\n持续校准模型"]];road.forEach((r,i)=>{const x=75+i*285;shape(s,x,235,235,195,i===0?C.teal:"#28546A","none",true);tx(s,r[0],x+20,260,195,24,16,C.mint,{bold:true});tx(s,r[1],x+20,315,195,80,20,C.white,{bold:true})});tx(s,"第一步：把消费者洞察变成可运行的维度库，并完成 20 条方案测试。",75,520,1080,30,20,C.mint,{bold:true});tx(s,"沙盘帮助团队更聚焦地验证方案，让洞察更容易复用。",75,625,1100,25,15,C.white,{italic:true});note(s,"结尾：消费者心智沙盘是独立产品；抚心是首个验证场景。")}

await (await PresentationFile.exportPptx(deck)).save(draft);
console.log(`draft=${draft}`); console.log(`final=${out}`);

