(()=>{
 const clamp=x=>Math.max(0,Math.min(1,x));
 const ease=x=>{x=clamp(x);return x*x*x*(x*(x*6-15)+10)};
 const mix=(a,b,t)=>a+(b-a)*t;
 function bounds(plan,target){
  if(target==='overview')return {x:0,y:0,width:plan.world.width,height:plan.world.height};
  const board=plan.boards.find(b=>b.id===target);if(board)return {x:board.x,y:board.y,width:board.width,height:board.height};
  const [id,focusId]=target.split('/'),component=plan.components.find(c=>c.id===id);
  if(!component)throw Error('找不到镜头目标：'+target);
  const owner=plan.boards.find(b=>b.id===component.board_id),box=component.bounds;
  const focus=focusId?(component.focuses||[]).find(f=>f.id===focusId)?.bounds:null;
  if(focusId&&!focus)throw Error('找不到局部关注框：'+target);
  return {x:owner.x+box.x+(focus?.x||0),y:owner.y+box.y+(focus?.y||0),width:focus?.width||box.width,height:focus?.height||box.height};
 }
 function fit(box,output,padding=.12){
  const framing=globalThis.CANVAS_PLAN?.framing;
  const browsing=globalThis.document?.body?.classList.contains('resource-mode');
  if(framing?.content_rect&&!browsing){
   const base=globalThis.CANVAS_PLAN.output,r=framing.content_rect;
   const rect={x:r.x*output.width/base.width,y:r.y*output.height/base.height,width:r.width*output.width/base.width,height:r.height*output.height/base.height};
   return {cx:box.x+box.width/2,cy:box.y+box.height/2,scale:Math.min(rect.width*(1-2*padding)/box.width,rect.height*(1-2*padding)/box.height),screen_cx:rect.x+rect.width/2,screen_cy:rect.y+rect.height/2};
  }
  const safeHeight=output.height-(globalThis.CanvasSubtitles?.reserve(output)||0);
  const scale=Math.min(output.width*(1-2*padding)/box.width,safeHeight*(1-2*padding)/box.height);
  return {cx:box.x+box.width/2,cy:box.y+box.height/2,scale};
 }
 function interpolate(a,b,u,travelScale){
  const q=ease(u),base=mix(Math.log(a.scale),Math.log(b.scale),q);
  const dip=travelScale?Math.max(0,Math.log(Math.sqrt(a.scale*b.scale)/travelScale)):0;
  const result={cx:mix(a.cx,b.cx,q),cy:mix(a.cy,b.cy,q),scale:Math.exp(base-dip*4*q*(1-q))};
  if(a.screen_cx!==undefined&&b.screen_cx!==undefined){result.screen_cx=mix(a.screen_cx,b.screen_cx,q);result.screen_cy=mix(a.screen_cy,b.screen_cy,q)}
  return result;
 }
 function at(plan,time){
  let index=0;for(let i=1;i<plan.shots.length;i++)if(time>=plan.shots[i].at)index=i;
  const shot=plan.shots[index],to=fit(bounds(plan,shot.target),plan.output,shot.padding??.12);
  if(index===0||shot.move===0)return {...to,index,shot};
  const previous=plan.shots[index-1],from=fit(bounds(plan,previous.target),plan.output,previous.padding??.12);
  return {...interpolate(from,to,(time-shot.at)/shot.move,shot.travel_scale),index,shot};
 }
 function matrix(camera,output){const reserve=globalThis.CanvasSubtitles?.reserve(output)||0;return `translate(${(camera.screen_cx??output.width/2)-camera.cx*camera.scale}px,${(camera.screen_cy??(output.height-reserve)/2)-camera.cy*camera.scale}px) scale(${camera.scale})`}
 globalThis.CanvasCamera={clamp,ease,mix,bounds,fit,interpolate,at,matrix};
})();
