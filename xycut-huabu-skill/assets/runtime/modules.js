(()=>{
 const definitions=new Map(),installed=new Set();
 const clamp=x=>Math.max(0,Math.min(1,x)),ease=x=>{x=clamp(x);return x*x*x*(x*(x*6-15)+10)};
 const phase=(t,start,duration=.4)=>ease((t-start)/duration);
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function cuesFor(value,count,spacing=1.5){
  const cues=value??Array.from({length:count},(_,i)=>.12+i*spacing);
  if(!Array.isArray(cues)||cues.length!==count||cues.some((v,i)=>!Number.isFinite(v)||v<0||(i>0&&v<=cues[i-1])))throw Error('组件cues需与条目数量相等，且为递增的非负秒数');
  return [...cues];
 }
 function register(definition){
  if(!definition.id||typeof definition.create!=='function'||definitions.has(definition.id))throw Error('模块定义无效或重复：'+definition.id);
  definitions.set(definition.id,definition);
 }
 function create(id,root,options={}){
  const definition=definitions.get(id);if(!definition)throw Error('尚未加载模块：'+id);
  const width=options.width??definition.size.width,height=options.height??definition.size.height;
  if(!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)throw Error('组件宽高必须大于零');
  if(!installed.has(id)){const style=document.createElement('style');style.dataset.moduleStyle=id;style.textContent=definition.css;document.head.append(style);installed.add(id)}
  root.replaceChildren();root.dataset.module=id;
  const icons=options.icons||window.CanvasIcons||{};
  const instance=definition.create(root,{...options,width,height,content:JSON.parse(JSON.stringify(options.content||{})),esc,phase,ease,clamp,cuesFor,icon:name=>icons[name]||icons.file||''});
  if(typeof instance?.render!=='function')throw Error('模块缺少render：'+id);
  return {id,root,render(time){if(!Number.isFinite(time))throw Error('模块时间必须为有限秒数');instance.render(Math.max(0,time))}};
 }
 window.CanvasModules={register,create,get:id=>definitions.get(id),ids:()=>[...definitions.keys()]};
})();
