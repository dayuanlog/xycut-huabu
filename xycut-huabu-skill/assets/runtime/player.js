(()=>{
 const P=window.CANVAS_PLAN,C=window.CanvasCamera,S=window.CanvasScene,$=s=>document.querySelector(s),world=$('#world'),screen=$('#screen'),stage=$('#stage');
 const params=new URLSearchParams(location.search),renderMode=params.get('render')==='1';
 let time=0,playing=false,frame=0,last=0,flight=0,mode='resource',selected='',drag=null,segment=null;
 let viewport={...P.output},browseTarget='overview',tool='select';
 let view=C.fit(C.bounds(P,'overview'),P.output,.025),current={...view};
 const names={headline:'开场文字',slider:'规则滑块',brand:'品牌标识',note:'方法说明',browser:'界面卡片',metric:'结果数字',input:'输入卡片',flow:'流程连线',features:'功能清单',tags:'标签组合',compare:'对比结构',media:'媒体插槽',statement:'句内关键词',quote:'收束金句',badge:'结果标识'};
 function setMode(next){mode=next;document.body.classList.toggle('resource-mode',mode==='resource');document.body.classList.toggle('demo-mode',mode==='demo')}
 function apply(camera){current={cx:camera.cx,cy:camera.cy,scale:camera.scale,screen_cx:camera.screen_cx,screen_cy:camera.screen_cy};world.style.transform=C.matrix(camera,viewport);$('#zoom-label').textContent=Math.round(camera.scale*100)+'%'}
 function pause(){playing=false;cancelAnimationFrame(frame);frame=0;$('#play').textContent='播放镜头演示'}
 function stop(){pause();cancelAnimationFrame(flight);flight=0}
 function clearOutline(){S.elements.forEach(el=>el.classList.remove('selected'))}
 function select(id){
  selected=id;clearOutline();const component=P.components.find(c=>c.id===id);if(!component)return;
  if(mode==='resource')S.elements.get(id).classList.add('selected');
  document.querySelectorAll('#library button').forEach(b=>b.classList.toggle('active',b.dataset.target===id));
  window.dispatchEvent(new CustomEvent('canvas-selection',{detail:{id}}));
 }
 function browse(){stop();segment=null;if(mode==='demo')browseTarget=null;setMode('resource');view={...current};S.render(P.duration);if(selected)select(selected);$('#shot-label').textContent='自由查看 · 组件已呈现完成状态'}
 function focus(target,immediate=false){
  stop();segment=null;setMode('resource');S.render(P.duration);clearOutline();
  const componentId=target.split('/')[0];if(P.components.some(c=>c.id===componentId))select(componentId);
  browseTarget=target;const from={...current},to=C.fit(C.bounds(P,target),viewport,target==='overview'?.025:.12);view=to;
  if(immediate){apply(to);return}
  const start=performance.now();function tick(now){const u=C.clamp((now-start)/750);apply(C.interpolate(from,to,u));if(u<1)flight=requestAnimationFrame(tick);else flight=0}flight=requestAnimationFrame(tick);
  $('#shot-label').textContent=target==='overview'?'完整资源画布':'自由构图 · '+target;
 }
 function renderAt(value){
  time=Math.max(0,Math.min(P.duration,Number(value)||0));cancelAnimationFrame(flight);flight=0;setMode('demo');clearOutline();
  S.render(time);const camera=segment?{...C.fit(C.bounds(P,segment.target),viewport,.08),index:0,shot:{target:segment.target,move:0,label:segment.label}}:C.at({...P,output:viewport},time);apply(camera);
  const previous=P.shots[Math.max(0,camera.index-1)],q=camera.shot.move?C.ease((time-camera.shot.at)/camera.shot.move):1;
  const matches=(component,target)=>target==='overview'||target===component.board_id||target.split('/')[0]===component.id;
  P.components.forEach(component=>{
   const strength=(matches(component,previous.target)?1:0)*(1-q)+(matches(component,camera.shot.target)?1:0)*q;
   const retained=camera.shot.retain?.includes(component.id);
   S.elements.get(component.id).style.filter='brightness('+(retained?Math.max(.8,.38+.62*strength):.38+.62*strength)+') blur('+(retained?0:(1-strength)*1.7/camera.scale)+'px)';
  });
  const [id,part]=camera.shot.target.split('/');
  if(part&&S.elements.get(id)?.classList.contains('kind-browser'))S.elements.get(id).querySelectorAll('.browser-content>*').forEach(child=>{
   const relevant=part==='actions'?child.classList.contains('browser-actions'):!child.classList.contains('browser-actions')&&!child.classList.contains('browser-fine');
   if(!relevant)child.style.filter='brightness('+C.mix(1,.4,q)+') blur('+(q*1.7/camera.scale)+'px)';
  });
  $('#seek').value=time;$('#time-label').textContent=(time-(segment?.start||0)).toFixed(2)+' / '+(segment?segment.end-segment.start:P.duration).toFixed(2)+' 秒';$('#shot-label').textContent=(segment?'局部预览':(camera.index+1)+' / '+P.shots.length)+' · '+camera.shot.label+' · 演示时钟';
  return time;
 }
 function tick(now){if(!playing)return;renderAt(Math.min(segment?.end??P.duration,time+Math.min(.1,(now-last)/1000)));last=now;if(time>=(segment?.end??P.duration))pause();else frame=requestAnimationFrame(tick)}
 function play(){if(playing){pause();return}if(time>=(segment?.end??P.duration))time=segment?.start||0;renderAt(time);playing=true;last=performance.now();$('#play').textContent='暂停';frame=requestAnimationFrame(tick)}
 function preview(target){
  stop();const members=P.components.filter(c=>c.id===target||c.board_id===target),timed=members.filter(c=>c.motion);
  if(!timed.length)return;segment={target,label:members.length===1?members[0].name:P.boards.find(b=>b.id===target)?.name,start:Math.min(...timed.map(c=>c.motion.start)),end:Math.max(...timed.map(c=>c.motion.start+c.motion.duration))};
  $('#seek').min=segment.start;$('#seek').max=segment.end;time=segment.start;play();
 }
 function fit(){
  const workspace=$('.workspace'),w=renderMode?innerWidth:workspace.clientWidth,h=renderMode?innerHeight:workspace.clientHeight;
  if(w<=0||h<=0)return;
  viewport=renderMode||P.framing?{...P.output}:{...P.output,height:P.output.width*h/w};
  const scale=renderMode||P.framing?Math.min(w/viewport.width,h/viewport.height):w/viewport.width;
  screen.style.width=w+'px';screen.style.height=h+'px';stage.style.width=viewport.width+'px';stage.style.height=viewport.height+'px';stage.style.transform='translate('+((w-viewport.width*scale)/2)+'px,'+((h-viewport.height*scale)/2)+'px) scale('+scale+')';
  cancelAnimationFrame(flight);flight=0;
  if(mode==='demo')renderAt(time);
  else {if(browseTarget)view=C.fit(C.bounds(P,browseTarget),viewport,browseTarget==='overview'?.025:.12);apply(view)}
 }
 P.boards.forEach((board,i)=>{
  const details=document.createElement('details');details.open=i===0;
  const summary=document.createElement('summary');summary.textContent=String(i+1).padStart(2,'0')+' · '+board.name;details.append(summary);
  const all=document.createElement('button');all.textContent='关注整个区域';all.dataset.target=board.id;all.onclick=()=>focus(board.id);details.append(all);
  if(P.components.some(c=>c.board_id===board.id&&c.motion)){const run=document.createElement('button');run.className='preview-entry';run.textContent='▷ 播放这个页面';run.onclick=()=>preview(board.id);details.append(run)}
  P.components.filter(c=>c.board_id===board.id).forEach(c=>{const b=document.createElement('button');b.textContent=(c.name||window.CanvasModules?.get(c.module_id)?.name||names[c.kind]||c.kind)+' · '+c.id;b.dataset.target=c.id;b.onclick=()=>{browse();select(c.id);focus(c.id)};details.append(b)});
  if(P.library_id)P.components.filter(c=>c.board_id===board.id&&c.motion).forEach(c=>{const run=document.createElement('button');run.className='preview-entry';run.textContent='▷ '+c.name;run.onclick=()=>preview(c.id);details.append(run)});
  $('#library').append(details);
 });
 function zoom(factor,pivot){
  browse();browseTarget=null;const old=view.scale,next=Math.max(.065,Math.min(6,old*factor));
  const point=pivot||{x:viewport.width/2,y:viewport.height/2},dx=point.x-viewport.width/2,dy=point.y-viewport.height/2;
  view={cx:view.cx+dx/old-dx/next,cy:view.cy+dy/old-dy/next,scale:next};apply(view);
 }
 function setTool(next){tool=next==='pan'?'pan':'select';document.body.classList.toggle('tool-pan',tool==='pan');document.body.classList.toggle('tool-select',tool==='select')}
 document.querySelectorAll('#world img').forEach(img=>img.draggable=false);
 screen.addEventListener('dragstart',e=>e.preventDefault());
 screen.addEventListener('wheel',e=>{e.preventDefault();const r=screen.getBoundingClientRect(),s=screen.clientWidth/P.output.width;zoom(Math.exp(-e.deltaY*.0013),{x:(e.clientX-r.left)/s,y:(e.clientY-r.top)/s})},{passive:false});
 screen.addEventListener('pointerdown',e=>{if(e.button!==0||renderMode)return;e.preventDefault();stop();if(tool==='pan')browse();else view={...current};drag={id:e.pointerId,x:e.clientX,y:e.clientY,camera:{...current},target:e.target,moved:false,tool};screen.setPointerCapture(e.pointerId);if(tool==='pan')screen.classList.add('dragging')});
 screen.addEventListener('pointermove',e=>{if(!drag||e.pointerId!==drag.id)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.hypot(dx,dy)>6)drag.moved=true;if(drag.tool!=='pan')return;browseTarget=null;screen.classList.add('dragging');const scale=screen.clientWidth/viewport.width;view={...drag.camera,cx:drag.camera.cx-dx/scale/drag.camera.scale,cy:drag.camera.cy-dy/scale/drag.camera.scale};apply(view)});
 function endDrag(e,cancelled=false){if(!drag||e.pointerId!==drag.id)return;const previous=drag;drag=null;screen.classList.remove('dragging');if(!cancelled&&previous.tool==='select'&&!previous.moved){const component=previous.target.closest('[data-component]');if(component){select(component.dataset.component);window.dispatchEvent(new CustomEvent('canvas-review-request',{detail:{id:component.dataset.component,point:{x:e.clientX,y:e.clientY}}}))}}}
 screen.addEventListener('pointerup',e=>endDrag(e));screen.addEventListener('pointercancel',e=>endDrag(e,true));screen.addEventListener('lostpointercapture',e=>endDrag(e,true));
 screen.addEventListener('dblclick',e=>{const component=e.target.closest('[data-component]');if(component)focus(component.dataset.component)});
 $('#overview').onclick=()=>focus('overview');$('#zoom-in').onclick=()=>zoom(1.3);$('#zoom-out').onclick=()=>zoom(1/1.3);$('#browse').onclick=browse;
 $('#play').onclick=play;$('#replay').onclick=()=>{stop();time=segment?.start||0;play()};$('#seek').max=P.duration;$('#time-label').textContent='0.00 / '+P.duration.toFixed(2)+' 秒';$('#seek').oninput=e=>{stop();renderAt(e.target.value)};
 const resetRange=()=>{if(!segment){$('#seek').min=0;$('#seek').max=P.duration}};
 document.addEventListener('click',resetRange);
 setTool('select');
 document.addEventListener('keydown',e=>{if(renderMode||e.target.closest('input,textarea,[contenteditable="true"],[role="dialog"]'))return;if(e.code==='Space'){e.preventDefault();setTool('pan');return}if(e.target.closest('button,summary'))return;if(e.key.toLowerCase()==='f')focus('overview')});
 document.addEventListener('keyup',e=>{if(e.code==='Space'){if(tool==='pan')e.preventDefault();setTool('select')}});
 window.addEventListener('blur',()=>{setTool('select');if(drag)endDrag({pointerId:drag.id},true)});
 if(renderMode)document.body.classList.add('render');
 window.renderAt=renderAt;window.END=P.duration;window.EXPORT_CANVAS_PLAN=()=>JSON.parse(JSON.stringify(P));
 window.CanvasExplorer={focus,browse,select,preview,overview:()=>focus('overview'),getView:()=>({...current}),getMode:()=>mode,getTime:()=>time,getSelected:()=>selected,getTool:()=>tool,pause};
 window.READY=Promise.all([document.fonts.ready,...[...document.images].map(img=>img.decode()),new Promise((resolve,reject)=>{const image=new Image;image.onload=resolve;image.onerror=reject;image.src=(P.asset_base||'../../')+'themes/tech-dark/background.jpg'})]).then(()=>{
  fit();if(renderMode)renderAt(params.get('t')||0);else {S.render(P.duration);apply(view)}window.__XYCUT_READY__=true;addEventListener('resize',fit);return true;
 });
})();
