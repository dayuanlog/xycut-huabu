(()=>{
 const P=window.CANVAS_PLAN,world=document.querySelector('#world'),elements=new Map(),instances=new Map(),icons=window.CanvasIcons;
 const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const icon=name=>icons[name]||icons.file;
 const logo=(P.asset_base||'../../')+'brand/icon.png',wordmark=(P.asset_base||'../../')+'brand/name.png';
 const chips=items=>items.map(t=>'<span>'+esc(t)+'</span>').join('');
 const markup={
  headline:c=>'<div class="headline-eyebrow">'+esc(c.eyebrow)+'</div>'+c.lines.map((x,i)=>'<div class="headline-line '+(i?'accent':'')+'"><span>'+esc(x)+'</span></div>').join(''),
  slider:c=>'<div class="slider-top"><span>'+esc(c.label)+'</span><b data-slider-number>0</b></div><div class="slider-track"><i></i><div class="slider-knob"></div></div><div class="slider-scale">'+Array.from({length:11},()=>'<i></i>').join('')+'</div><div class="slider-labels"><span>'+esc(c.left)+'</span><span>'+esc(c.right)+'</span></div>',
  brand:c=>'<div class="brand-logo"><img src="'+logo+'" alt="XYCut 图标"></div><div class="brand-type"><img src="'+wordmark+'" alt="XYCut"><p>'+esc(c.label)+'</p></div>',
  note:c=>'<div class="note-mark"></div><div><b>'+esc(c.title)+'</b><p>'+esc(c.detail)+'</p></div>',
  browser:c=>'<div class="browser-bar"><i></i><i></i><i></i><span>XYCut / Canvas</span></div><div class="browser-content"><div class="browser-kicker">一个想法，一条连续的讲解</div><h2>'+esc(c.title)+'</h2><p>'+esc(c.caption)+'</p><div class="browser-actions"><span>'+icon('file')+'内容</span><span>'+icon('edit')+'结构</span><span class="active">'+icon('check')+'可修改</span></div><div class="browser-fine">局部构图 · 连续镜头 · 语义动画</div></div>',
  metric:c=>'<div class="metric-label">'+esc(c.label)+'</div><div class="metric-number"><b>0</b><span>'+esc(c.suffix)+'</span></div><div class="metric-spark">✦</div><p>'+esc(c.detail)+'</p>',
  input:c=>'<div class="input-icon">'+icon('file')+'</div><h2>'+esc(c.title)+'</h2><div class="input-lines"><i></i><i></i><i></i></div><div class="input-tags">'+chips(c.lines)+'</div>',
  flow:c=>'<svg class="flow-lines" viewBox="0 0 850 435" aria-hidden="true"><path d="M110 220C240 70 290 365 425 220S630 70 740 220"/><circle r="9"/></svg>'+c.labels.map((label,i)=>'<div class="flow-node node-'+i+'"><span>0'+(i+1)+'</span>'+icon(['search','database','play'][i])+'<b>'+esc(label)+'</b></div>').join(''),
  features:c=>c.items.map((x,i)=>'<article class="feature-card"><div class="feature-top"><span>0'+(i+1)+'</span>'+icon(x.icon)+'</div><div class="feature-art art-'+i+'"><i></i><i></i><i></i></div><b>'+esc(x.title)+'</b><p>'+esc(x.detail)+'</p></article>').join(''),
  tags:c=>chips(c.items),
  compare:c=>'<div class="compare-top"><span>'+(c.tidy?'02':'01')+'</span><h2>'+esc(c.title)+'</h2></div><div class="compare-pile">'+c.labels.map((label,i)=>'<div data-piece="'+i+'">'+icon(['file','edit','check'][i])+'<span>'+esc(label)+'</span></div>').join('')+'</div>',
  media:c=>'<div class="media-bar"><i></i><i></i><i></i><span>'+esc(c.label)+'</span></div><div class="media-screen"><div class="media-slice a"></div><div class="media-slice b"></div><div class="media-words"><span>SHOW / EXPLAIN / CREATE</span><b>'+esc(c.title)+'</b></div><div class="media-play">'+icon('play')+'</div></div><div class="media-controls"><span>▶</span><div><i></i></div><span>00:12</span></div>',
  statement:c=>'<div class="statement-line"><span>'+esc(c.prefix)+'</span><div class="statement-reel">'+c.words.map(w=>'<b>'+esc(w)+'</b>').join('')+'</div><span>'+esc(c.suffix)+'</span></div><div class="statement-result">'+esc(c.result)+'</div>',
  quote:c=>'<div class="quote-sign">“</div>'+c.lines.map(x=>'<div class="quote-line"><span>'+esc(x)+'</span></div>').join(''),
  badge:c=>icon('check')+'<span>'+esc(c.label)+'</span>'
 };
 world.style.width=P.world.width+'px';world.style.height=P.world.height+'px';
 P.boards.forEach((board,i)=>{
  const node=document.createElement('section');node.className='board board-'+board.id;node.dataset.board=board.id;
  Object.assign(node.style,{left:board.x+'px',top:board.y+'px',width:board.width+'px',height:board.height+'px'});
  node.innerHTML='<div class="board-label"><span>0'+(i+1)+'</span>'+esc(board.name)+'</div><div class="board-grain"></div>';
  world.append(node);
  P.components.filter(c=>c.board_id===board.id).forEach(component=>{
   const el=document.createElement('div');el.className='component kind-'+component.kind;el.dataset.component=component.id;
   const b=component.bounds;Object.assign(el.style,{left:b.x+'px',top:b.y+'px',width:b.width+'px',height:b.height+'px'});
   node.append(el);elements.set(component.id,el);
   if(component.kind==='library'){
    const design=component.design_size;let host=el;
    if(design){
     host=document.createElement('div');host.className='module-design';
     const scale=Math.min(b.width/design.width,b.height/design.height);
     Object.assign(host.style,{position:'absolute',width:design.width+'px',height:design.height+'px',left:(b.width-design.width*scale)/2+'px',top:(b.height-design.height*scale)/2+'px',transformOrigin:'0 0',transform:'scale('+scale+')'});el.append(host);
    }
    instances.set(component.id,window.CanvasModules.create(component.module_id,host,{content:component.content,width:design?.width||b.width,height:design?.height||b.height,cues:component.motion?.cues,icons}));
   }
   else el.innerHTML=markup[component.kind](component.content);
  });
 });
 const phase=(t,start,end)=>CanvasCamera.ease((t-start)/(end-start));
 function progress(id,time){const beat=P.beats.find(b=>b.component_id===id);return beat?phase(time,beat.start,beat.end):1}
 function render(time){
  for(const component of P.components){
   const el=elements.get(component.id),u=progress(component.id,time),type=component.kind;el.style.filter='';
   el.querySelectorAll('.browser-content>*').forEach(child=>child.style.filter='');
   if(type==='library'){instances.get(component.id).render(Math.min(component.motion?.duration??Infinity,Math.max(0,time-(component.motion?.start||0))));continue}
   if(type==='headline'||type==='quote'){
    el.querySelectorAll('.headline-line span,.quote-line span').forEach((line,i)=>{const q=CanvasCamera.ease(u*1.4-i*.32);line.style.transform='translateY('+(105*(1-q))+'%)';line.style.opacity=q});
   }else if(type==='slider'){
    el.querySelector('[data-slider-number]').textContent=Math.round(component.content.value*u);el.querySelector('.slider-track i').style.width=(component.content.value*u)+'%';el.querySelector('.slider-knob').style.left=(component.content.value*u)+'%';
   }else if(type==='metric')el.querySelector('.metric-number b').textContent=(component.content.value*u).toFixed(1);
   else if(type==='flow'){
    const path=el.querySelector('path'),length=path.getTotalLength(),point=path.getPointAtLength(length*u);path.style.strokeDasharray=length;path.style.strokeDashoffset=length*(1-u);const dot=el.querySelector('circle');dot.setAttribute('cx',point.x);dot.setAttribute('cy',point.y);dot.style.opacity=u>0&&u<1?1:0;
    el.querySelectorAll('.flow-node').forEach((node,i)=>{const q=CanvasCamera.ease(u*1.45-i*.22);node.style.opacity=q;node.style.transform='translateY('+(24*(1-q))+'px)'});
   }else if(type==='features')el.querySelectorAll('article').forEach((card,i)=>{const q=CanvasCamera.ease(u*1.6-i*.28);card.style.opacity=q;card.style.transform='translateY('+(45*(1-q))+'px) scale('+(.96+.04*q)+')'});
   else if(type==='compare')el.querySelectorAll('[data-piece]').forEach((piece,i)=>{
    const tidy=component.content.tidy?u:0;piece.style.transform='translate('+([8,-12,16][i]*(1-tidy))+'px,'+([8,-8,3][i]*(1-tidy))+'px) rotate('+([-8,7,-5][i]*(1-tidy))+'deg)';
   });
   else if(type==='statement'){
    const beat=P.beats.find(b=>b.component_id===component.id),start=beat?.start||0,span=beat?beat.end-beat.start:1;
    const position=phase(time,start+span*.25,start+span*.48)+phase(time,start+span*.66,start+span*.89);el.querySelectorAll('.statement-reel b').forEach((word,i)=>word.style.transform='translateY('+((i-position)*136)+'px)');
   }else if(type==='media')el.querySelector('.media-controls i').style.width=(8+84*u)+'%';
   else if(type==='browser')el.querySelectorAll('.browser-actions span').forEach((button,i)=>button.classList.toggle('active',i===Math.min(2,Math.floor(u*3))));
   else if(type==='brand'||type==='note'||type==='input'){el.style.opacity=.25+.75*u;el.style.transform='translateY('+(20*(1-u))+'px)'}
  }
 }
 globalThis.CanvasScene={elements,instances,render,markup};
})();
