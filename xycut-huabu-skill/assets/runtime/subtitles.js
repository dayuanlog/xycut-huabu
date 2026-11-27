/* 固定画面字幕层。复制到项目后按本次最终时间轴与主题显式初始化。 */
(()=>{
 let sequence=0;
 const modes=['emphasis','normal','off'],clamp=x=>Math.max(0,Math.min(1,x)),ease=x=>{x=clamp(x);return x*x*(3-2*x)};
 function create({stage,timeline,output={width:1920,height:1080},config={},mode:requestedMode,isBrowsing=()=>document.body.classList.contains('resource-mode'),requestRender}={}){
  if(!stage||!Array.isArray(timeline?.lines))throw Error('字幕需要输出容器和最终时间轴lines');
  const settings={mode:'emphasis',reveal:'typewriter',font_size:54,line_height:1.45,bottom:54,safe_bottom:216,margin_x:Math.min(120,output.width*.08),hold_seconds:.18,color:'#f7fafc',accent:'#00c1cd',keywords:{},strong_lines:[],display_aliases:{},...JSON.parse(JSON.stringify(config))};
  let mode=requestedMode??settings.mode,active=null,units=[],sheen=null,lastTime=0;
  if(!modes.includes(mode)||!['typewriter','sentence'].includes(settings.reveal))throw Error('字幕模式无效');
  for(const key of ['font_size','line_height','bottom','safe_bottom','margin_x','hold_seconds'])if(!Number.isFinite(settings[key])||settings[key]<(key==='font_size'||key==='line_height'?.01:0))throw Error('字幕数值无效 '+key);
  if(settings.margin_x*2>=output.width)throw Error('字幕左右边距超出输出宽度');
  if(settings.top!=null&&(!Number.isFinite(settings.top)||settings.top<0||settings.top>=output.height))throw Error('字幕上沿超出输出高度');
  const placement=settings.top==null?`bottom:${settings.bottom}px`:`top:${settings.top}px;bottom:auto`;
  settings.mode=mode;
  const recipes=timeline.lines.map(line=>{
   const text=String(line.text??''),start=line.target_start_ms/1000,end=line.target_end_ms/1000;
   if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start)throw Error('字幕行时间无效 '+line.line_id);
   const source=line.tokens||[],aliases=settings.display_aliases[line.line_id]||[],consumed=new Set();
   const tokens=source.flatMap(token=>{
    if(consumed.has(token.token_id))return [];
    const alias=aliases.find(a=>a.token_ids.includes(token.token_id));if(!alias)return [token];
    const originals=source.filter(t=>alias.token_ids.includes(t.token_id));
    if(originals.length!==alias.token_ids.length||!alias.text)throw Error('字幕专名映射无效 '+line.line_id);
    originals.forEach(t=>consumed.add(t.token_id));
    const offset=text.indexOf(alias.text);return [{...token,text:alias.text,source_char_start:offset,source_char_end:offset+alias.text.length,target_start_ms:originals[0].target_start_ms,target_end_ms:originals.at(-1).target_end_ms}];
   });
   const ranges=(settings.keywords[line.line_id]||[]).flatMap(word=>{const offset=text.indexOf(word);if(offset<0)throw Error('字幕强调词不在本句中 '+line.line_id+':'+word);return [{start:offset,end:offset+word.length}]});
   const pieces=[];let offset=0;
   function add(value,from,to,at,tokenId){
    if(!value)return;
    const edges=[...new Set([from,to,...ranges.flatMap(r=>[r.start,r.end]).filter(x=>x>from&&x<to)])].sort((a,b)=>a-b);
    for(let i=0;i<edges.length-1;i++){const a=edges[i],b=edges[i+1];pieces.push({text:text.slice(a,b),at,tokenId,keyword:ranges.some(r=>a<r.end&&b>r.start)})}
   }
   for(let i=0;i<tokens.length;i++){
    const token=tokens[i];let from=token.source_char_start,to=token.source_char_end;
    if(!Number.isInteger(from)||!Number.isInteger(to)||text.slice(from,to).toLowerCase()!==String(token.text).toLowerCase()){
     from=text.toLowerCase().indexOf(String(token.text).toLowerCase(),offset);to=from+String(token.text).length;
    }
    if(from<offset||from<0||text.slice(from,to).toLowerCase()!==String(token.text).toLowerCase())throw Error('字幕字词无法对齐，请提供display_aliases '+line.line_id+'/'+token.token_id);
    const at=token.target_start_ms/1000;
    if(!Number.isFinite(at)||at<start-.001||at>end)throw Error('字幕字词时间超出本句 '+line.line_id);
    add(text.slice(offset,from),offset,from,i?tokens[i-1].target_end_ms/1000:at,'punctuation');
    add(text.slice(from,to),from,to,at,token.token_id);offset=to;
   }
   add(text.slice(offset),offset,text.length,tokens.length?tokens.at(-1).target_start_ms/1000:start,'punctuation');
   return {id:line.line_id,text,start,end,pieces,wordTimed:tokens.length>0,strong:settings.strong_lines.includes(line.line_id)};
  });
  if(recipes.some((r,i)=>i&&r.start<recipes[i-1].start))throw Error('字幕行必须按最终时间排序');
  const id='canvas-subtitles-'+(++sequence),root=document.createElement('div');root.id=id;root.setAttribute('aria-hidden','true');root.dataset.timelineRevision=timeline.timeline_revision||'';
  root.innerHTML='<div class="canvas-caption-shade"></div><div class="canvas-caption-placement"><div class="canvas-caption-line"><span class="canvas-caption-units"></span><i class="canvas-caption-cursor"></i></div></div>';
  stage.append(root);
  const css=document.createElement('style');css.textContent=`
  #${id}{position:absolute;inset:0;z-index:40;pointer-events:none;overflow:hidden;--caption-glint:-20%}
  #${id} .canvas-caption-shade{position:absolute;bottom:0;left:0;right:0;height:${settings.safe_bottom+10}px;background:linear-gradient(transparent,rgba(5,9,14,.67))}
  #${id} .canvas-caption-placement{position:absolute;${placement};left:${settings.margin_x}px;right:${settings.margin_x}px;text-align:center}
  #${id} .canvas-caption-line{display:inline-block;position:relative;max-width:100%;text-align:center;font-family:inherit;font-size:${settings.font_size}px;font-weight:650;line-height:${settings.line_height};letter-spacing:.6px;color:${settings.color};text-shadow:0 3px 7px #000,0 1px 2px #000;-webkit-text-stroke:.35px #111b24;paint-order:stroke fill}
  #${id} .canvas-caption-unit{display:inline-block;max-width:100%;white-space:pre-wrap;vertical-align:baseline}
  #${id}[data-mode="emphasis"] .canvas-caption-keyword{color:${settings.accent};text-decoration:underline;text-decoration-color:${settings.accent};text-decoration-thickness:3px;text-underline-offset:8px}
  #${id} .canvas-caption-cursor{position:absolute;display:block;width:3px;height:${settings.font_size-1}px;background:#c9ffff;box-shadow:0 0 12px ${settings.accent};border-radius:2px}
  #${id} .canvas-caption-sheen{position:absolute;inset:0;pointer-events:none;user-select:none;color:#eaffff;text-shadow:0 0 17px #72f5ff;mask-image:linear-gradient(105deg,transparent calc(var(--caption-glint) - 10%),#000 var(--caption-glint),transparent calc(var(--caption-glint) + 10%));-webkit-text-stroke:0}
  `;document.head.append(css);
  const textRoot=root.querySelector('.canvas-caption-units'),lineNode=root.querySelector('.canvas-caption-line'),cursor=root.querySelector('.canvas-caption-cursor');
  function mount(recipe){
   active=recipe;textRoot.replaceChildren();sheen?.remove();sheen=null;
   units=recipe.pieces.map(piece=>{const node=document.createElement('span');node.className='canvas-caption-unit';node.textContent=piece.text;node.dataset.token=piece.tokenId;textRoot.append(node);return {...piece,node}});
   if(recipe.strong){sheen=document.createElement('span');sheen.className='canvas-caption-sheen';sheen.textContent=recipe.text;sheen.setAttribute('aria-hidden','true');lineNode.append(sheen)}
   root.dataset.lineId=recipe.id;
  }
  function render(t){
   if(!Number.isFinite(t))throw Error('字幕时间必须为有限秒数');lastTime=t;root.dataset.mode=mode;
   root.style.display=mode==='off'||isBrowsing()?'none':'block';
   if(mode==='off'||isBrowsing())return;
   let index=-1;for(let i=0;i<recipes.length;i++){if(t>=recipes[i].start)index=i;else break}
   const recipe=recipes[index],next=recipes[index+1];
   if(!recipe||t>=Math.min(next?.start??Infinity,recipe.end+settings.hold_seconds)){root.style.opacity='0';return}
   if(active!==recipe)mount(recipe);
   root.style.opacity=String(ease((t-recipe.start)/.07)*(1-ease((t-recipe.end)/Math.max(.001,settings.hold_seconds))));
   let last=null;const typing=settings.reveal==='typewriter'&&recipe.wordTimed;
   for(const unit of units){
    const spoken=t>=unit.at,visible=!typing||spoken;
    unit.node.style.opacity=visible?String(!typing?1:.55+.45*ease((t-unit.at)/.055)):'0';unit.node.style.visibility=visible?'visible':'hidden';
    unit.node.classList.toggle('canvas-caption-keyword',unit.keyword&&spoken);if(spoken)last=unit;
   }
   if(typing&&last&&t<recipe.end+.08){cursor.style.left=(last.node.offsetLeft+last.node.offsetWidth+7)+'px';cursor.style.top=(last.node.offsetTop+settings.font_size*.2)+'px';cursor.style.opacity=String((.6+.25*Math.cos((t-recipe.start)*Math.PI*3.2))*(1-ease((t-recipe.end)/.08)))}else cursor.style.opacity='0';
   if(sheen){const q=clamp((t-recipe.end+.48)/.55);root.style.setProperty('--caption-glint',(-20+140*q)+'%');sheen.style.opacity=mode==='emphasis'&&q>0&&q<1?String(.58*Math.sin(Math.PI*q)):0;sheen.style.clipPath=`inset(0 ${Math.max(0,lineNode.clientWidth-(last?last.node.offsetLeft+last.node.offsetWidth:0))}px 0 0)`}
  }
  function reserve(viewport=output){return mode==='off'||isBrowsing()||!recipes.length?0:Math.min(settings.safe_bottom,viewport.height*.4)}
  function setMode(value){if(!modes.includes(value))throw Error('字幕模式无效 '+value);mode=value;settings.mode=value;render(lastTime);return requestRender?.()}
  render(0);
  return {root,settings,render,reserve,setMode,getMode:()=>mode,destroy(){root.remove();css.remove();mode='off'}};
 }
 globalThis.CanvasSubtitleTrack={create};
})();
