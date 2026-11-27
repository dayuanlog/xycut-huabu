#!/usr/bin/env node
/* 仅验证字幕行为；使用测试时间，不生成或修改项目ASR。 */
import path from 'node:path';import {fileURLToPath,pathToFileURL} from 'node:url';
const args=process.argv.slice(2),value=name=>args[args.indexOf(name)+1];
if(!args.includes('--playwright-module')||!args.includes('--browser'))throw Error('需要 --playwright-module PATH 和 --browser PATH');
const {chromium}=await import(pathToFileURL(path.resolve(value('--playwright-module'))).href);
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const browser=await chromium.launch({executablePath:path.resolve(value('--browser')),headless:true});
try{
 const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<style>body{margin:0;font-family:sans-serif}#stage{position:relative;width:1920px;height:1080px}</style><body class="demo-mode"><div id="stage"></div></body>');
 await page.addScriptTag({path:path.join(root,'assets/runtime/camera.js')});await page.addScriptTag({path:path.join(root,'assets/runtime/subtitles.js')});
 const result=await page.evaluate(async()=>{
  const assert=(condition,message)=>{if(!condition)throw Error(message)},text='展示重点内容';
  const timeline={timeline_revision:'test-fixture-only',lines:[
   {line_id:'first',text,target_start_ms:0,target_end_ms:1800,tokens:[...text].map((c,i)=>({token_id:'t'+i,text:c,source_char_start:i,source_char_end:i+1,target_start_ms:i*250,target_end_ms:i*250+230}))},
   {line_id:'name',text:'打开 Workbuddy',target_start_ms:2000,target_end_ms:3600,tokens:[{token_id:'a',text:'打开',target_start_ms:2000,target_end_ms:2300},{token_id:'b',text:'Walkie',target_start_ms:2500,target_end_ms:2900},{token_id:'c',text:'Talkie',target_start_ms:2900,target_end_ms:3600}]},
   {line_id:'sentence',text:'整句字幕示例',target_start_ms:4000,target_end_ms:5500,tokens:[]}
  ]};
  const config={keywords:{first:['重点'],sentence:['字幕']},strong_lines:['first'],display_aliases:{name:[{text:'Workbuddy',token_ids:['b','c']}]}};
  let track=CanvasSubtitleTrack.create({stage:document.querySelector('#stage'),timeline,config});window.CanvasSubtitles=track;
  const units=()=>[...track.root.querySelectorAll('.canvas-caption-unit')],visible=()=>units().filter(n=>getComputedStyle(n).visibility==='visible').map(n=>n.textContent).join('');
  track.render(.3);const early=visible(),left=track.root.querySelector('.canvas-caption-line').getBoundingClientRect().left;assert(early==='展示','出现了未来字词');
  track.render(1.4);assert(visible()===text,'句尾漏字');assert(left===track.root.querySelector('.canvas-caption-line').getBoundingClientRect().left,'单句打字时排版跳动');
  track.render(.3);assert(visible()===early,'回退后字幕状态不同');
  track.render(3.5);assert(visible()==='打开 Workbuddy','专名映射或时间范围不正确');
  track.render(4.2);assert(visible()==='整句字幕示例','行级字幕没有整句显示');assert([...track.root.querySelectorAll('.canvas-caption-keyword')].map(n=>n.textContent).join('')==='字幕','行级字幕强调扩散到整句');
  const bright=getComputedStyle(track.root.querySelector('.canvas-caption-keyword')).color;await track.setMode('normal');assert(getComputedStyle(track.root.querySelector('.canvas-caption-keyword')).color!==bright,'普通模式未关闭强调');
  const box={x:0,y:0,width:1200,height:900},out={width:1920,height:1080};const before=CanvasCamera.fit(box,out).scale;
  await track.setMode('off');assert(getComputedStyle(track.root).display==='none'&&track.reserve(out)===0,'关闭后仍占字幕区');assert(CanvasCamera.fit(box,out).scale>before,'关闭后镜头未恢复');
  await track.setMode('emphasis');document.body.className='resource-mode';track.render(1);assert(getComputedStyle(track.root).display==='none'&&track.reserve(out)===0,'自由浏览仍显示字幕');document.body.className='demo-mode';
  track.destroy();track=CanvasSubtitleTrack.create({stage:document.querySelector('#stage'),timeline,config:{...config,reveal:'sentence'}});track.render(.1);assert(visible()===text,'整句模式仍逐字显示');assert(!track.root.querySelector('.canvas-caption-keyword'),'未读到关键词就强调');
  return {wordTiming:true,lineTiming:true,aliases:true,fixedLayout:true,rewind:true,modes:true,cameraSafety:true,browseHidden:true,sentenceReveal:true};
 });
 if(errors.length)throw Error(errors.join('\n'));console.log(JSON.stringify({ok:true,...result}));
}finally{await browser.close()}
