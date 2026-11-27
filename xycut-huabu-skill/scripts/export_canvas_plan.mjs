import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const [input,output,...flags]=process.argv.slice(2);
if(!input||!output){console.error('用法：node export_canvas_plan.mjs canvas-plan.js canvas-plan.json [--overwrite]');process.exit(1)}
if(fs.existsSync(output)&&!flags.includes('--overwrite'))throw Error('输出已存在，使用其他路径或明确指定--overwrite');
const context={window:{}};vm.runInNewContext(fs.readFileSync(input,'utf8'),context,{timeout:1000});
const plan=context.window.CANVAS_PLAN;if(!plan||typeof plan!=='object')throw Error('输入没有导出window.CANVAS_PLAN');
fs.mkdirSync(path.dirname(path.resolve(output)),{recursive:true});fs.writeFileSync(output,JSON.stringify(plan,null,2)+'\n','utf8');
console.log(JSON.stringify({ok:true,boards:plan.boards.length,components:plan.components.length,shots:plan.shots.length}));
