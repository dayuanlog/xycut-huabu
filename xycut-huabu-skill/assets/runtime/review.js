(()=>{
 if(new URLSearchParams(location.search).get('render')==='1')return;
 const P=window.CANVAS_PLAN,E=window.CanvasExplorer,$=s=>document.querySelector(s),editor=$('#review-editor'),input=$('#review-input');
 const key='xycut-canvas-review:v1:'+P.id+':'+location.pathname,drafts=new Map();
 let notes=[],active=null,editing=null;
 try{const saved=JSON.parse(localStorage.getItem(key)||'[]');if(Array.isArray(saved))notes=saved.filter(n=>n&&typeof n.id==='string'&&typeof n.component_id==='string'&&typeof n.instruction==='string'&&n.context)}catch{}
 const source=relative=>{const url=new URL(relative,location.href);return url.protocol==='file:'?decodeURIComponent(url.pathname).replace(/^\/([A-Za-z]:)/,'$1'):url.href};
 const status=text=>$('#review-status').textContent=text;
 function context(id){
  const c=P.components.find(c=>c.id===id);if(!c)return null;
  const board=P.boards.find(b=>b.id===c.board_id),mode=E.getMode(),time=E.getTime(),shot=mode==='demo'?P.shots.filter(s=>s.at<=time).at(-1):null;
  return JSON.parse(JSON.stringify({canvas_id:P.id,timeline_revision:P.timeline_revision,entry:source('index.html'),plan_source:source('canvas-plan.js'),theme_css:source('theme.css'),scene_source:source((P.asset_base||'../../')+'runtime/scene.js'),module_source:c.module_source?source(c.module_source):null,library_id:P.library_id||null,board:{id:board.id,name:board.name,x:board.x,y:board.y},component:c,view_mode:mode,render_time:mode==='demo'?time:null,shot:shot?{id:shot.id,target:shot.target,label:shot.label}:null}));
 }
 function persist(){try{localStorage.setItem(key,JSON.stringify(notes));return true}catch{status('已记录，但浏览器无法持久保存；请复制保存，刷新后可能丢失。');return false}}
 function close(){if(active&&!editing)drafts.set(active,input.value);editor.hidden=true;active=null;editing=null}
 function position(point){
  $('.workspace').append(editor);editor.classList.remove('docked');
  const screen=$('#screen').getBoundingClientRect(),width=Math.min(360,screen.width-24);editor.style.width=width+'px';
  const height=editor.offsetHeight,element=window.CanvasScene.elements.get(active)?.getBoundingClientRect();
  const center=element?element.left+element.width/2:screen.left+screen.width/2;
  const candidates=element?[[center-width/2,element.bottom+14],[center-width/2,element.top-height-14],[element.right+14,element.top],[element.left-width-14,element.top]]:[];
  candidates.push([screen.left+16,screen.bottom-height-16],[screen.right-width-16,screen.bottom-height-16],[screen.left+16,screen.top+16],[screen.right-width-16,screen.top+16]);
  const visible=[...window.CanvasScene.elements.values()].filter(el=>Number(getComputedStyle(el).opacity)>.01).map(el=>el.getBoundingClientRect()).filter(r=>r.right>screen.left&&r.left<screen.right&&r.bottom>screen.top&&r.top<screen.bottom);
  for(const [x,y] of candidates){
   const left=Math.max(screen.left+12,Math.min(x,screen.right-width-12)),top=Math.max(screen.top+12,Math.min(y,screen.bottom-height-12));
   const overlaps=visible.some(r=>left<r.right+8&&left+width>r.left-8&&top<r.bottom+8&&top+height>r.top-8);
   if(!overlaps){editor.style.left=left+'px';editor.style.top=top+'px';return}
  }
  $('#review-composer-slot').append(editor);editor.classList.add('docked');editor.style.removeProperty('width');editor.style.removeProperty('left');editor.style.removeProperty('top');
 }
 function open(id,options={}){
  const note=options.noteId?notes.find(n=>n.id===options.noteId):null;
  if(!context(id)&&!note){status('当前画布中找不到这个元素，请把记录复制给 Agent 按编号检查。');return}
  close();E.pause();active=id;editing=note?.id||null;input.value=note?.instruction??drafts.get(id)??'';$('#review-save').setAttribute('aria-label',editing?'确认修改':'确认添加');editor.hidden=false;position(options.point);input.focus();
 }
 function buildPrompt(items=notes){
  if(!items.length)return '';
  const header=['请修改以下画布视频项目。按组件稳定 ID 和源码路径定位，不要按浏览器截图中的坐标直接改世界坐标。','这些是用户记录的修改意见，请逐项处理。未提及的内容保持原设计；涉及尺寸或位置变化时，同时检查局部关注框、镜头构图和相邻元素。','自由查看模式的画面是组件完成状态；只有 render_time 非空的记录才指向演示中的具体秒数。','修改后先交付可检查的 HTML 预览，不自动渲染 MP4。'];
  return header.join('\n')+'\n\n'+items.map((n,i)=>'## '+(i+1)+' · '+n.component_id+'\n修改要求：\n'+n.instruction+'\n\n定位上下文：\n'+JSON.stringify(n.context,null,2)).join('\n\n');
 }
 async function copy(items){
  const text=buildPrompt(items);if(!text)return;
  try{if(!navigator.clipboard?.writeText)throw Error('clipboard unavailable');await navigator.clipboard.writeText(text)}catch{
   const field=$('#review-copy-output');field.hidden=false;field.value=text;field.focus();field.select();
   let copied=false;try{copied=document.execCommand('copy')}catch{}
   if(!copied){status('无法自动复制，请选中下方提示词手动复制。');return}field.hidden=true;
  }
  status('已复制 '+items.length+' 条修改意见，可粘贴给 Agent。');
 }
 function button(label,action){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=action;return b}
 function render(){
  const list=$('#review-list');list.replaceChildren();$('#review-count').textContent=notes.length;$('#review-copy-all').disabled=!notes.length;
  if(!notes.length){const empty=document.createElement('p');empty.className='review-empty';empty.textContent='暂无修改记录';list.append(empty)}
  notes.forEach((note,i)=>{
   const row=document.createElement('article');row.className='review-note';row.dataset.note=note.id;
   const title=document.createElement('b');title.textContent=String(i+1).padStart(2,'0')+' · '+note.component_id;
   const content=document.createElement('p');content.textContent=note.instruction;
   const meta=document.createElement('small');meta.textContent=(note.context.board?.name||'画布元素')+(note.context.render_time!=null?' · '+Number(note.context.render_time).toFixed(2)+' 秒':' · 自由查看');
   const actions=document.createElement('div');actions.className='review-note-actions';
   actions.append(button('定位',()=>{if(P.components.some(c=>c.id===note.component_id)){close();E.focus(note.component_id)}else status('元素编号已变化，请复制记录给 Agent 检查。')}),button('编辑',()=>open(note.component_id,{noteId:note.id})),button('复制',()=>copy([note])),button('删除',()=>{notes=notes.filter(n=>n.id!==note.id);if(editing===note.id)close();persist();render()}));
   row.append(title,content,meta,actions);list.append(row);
  });
 }
 function save(){
  const instruction=input.value.trim();if(!active||!instruction){input.focus();return}
  const existing=editing?notes.find(n=>n.id===editing):null,ctx=context(active)||existing?.context;
  if(!ctx){status('未找到元素，未保存。');return}
  const note={id:existing?.id||globalThis.crypto?.randomUUID?.()||Date.now()+'-'+Math.random().toString(36).slice(2),component_id:active,instruction,context:existing?.context||ctx,updated_at:new Date().toISOString()};
  if(existing)notes=notes.map(n=>n.id===existing.id?note:n);else notes.push(note);
  drafts.delete(active);editor.hidden=true;active=null;editing=null;render();if(persist())status('已记录并保存在当前浏览器，可编辑或复制给 Agent。');$('#review-list').lastElementChild?.scrollIntoView({block:'nearest'});
 }
 $('#review-save').innerHTML=window.CanvasIcons.check;$('#review-save').onclick=save;$('#review-copy-all').onclick=()=>copy(notes);
 input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.isComposing&&e.keyCode!==229){e.preventDefault();save()}});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!editor.hidden){e.preventDefault();close()}});
 window.addEventListener('canvas-review-request',e=>open(e.detail.id,{point:e.detail.point}));
 window.addEventListener('canvas-selection',e=>{if(active&&active!==e.detail.id)close()});
 $('#screen').addEventListener('pointerdown',close);$('#screen').addEventListener('wheel',close,{passive:true});
 $('#screen').addEventListener('dblclick',close);$('#library').addEventListener('click',close);
 ['play','replay','overview','browse','zoom-in','zoom-out'].forEach(id=>$('#'+id).addEventListener('click',close));
 $('#seek').addEventListener('input',close);window.addEventListener('resize',()=>{if(!editor.hidden)position()});
 window.CanvasReview={open,close,buildPrompt,getNotes:()=>JSON.parse(JSON.stringify(notes))};render();
})();
