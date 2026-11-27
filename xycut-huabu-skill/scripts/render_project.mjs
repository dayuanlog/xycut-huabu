#!/usr/bin/env node
/* 本地确定性渲染：逐帧调用 renderAt(t)，经 image2pipe 输出无声 H.264。 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { spawn, spawnSync } from 'node:child_process';

const HELP = `用法：node render_project.mjs ENTRY.html [参数]

输出模式（三选一）：
  --output FILE.mp4             输出新的无声 H.264 MP4，拒绝覆盖
  --stills-dir NEW_DIR          输出预览帧目录，需同时传 --times
  --probe                       仅读取页面 END 与画布信息

渲染参数：
  --times 0,1.5,3               预览帧绝对时间（秒）
  --start 0 --end SECONDS       视频区间；end 默认读取 window.END
  --fps 60                      输出帧率
  --width 1920 --height 1080    浏览器视口与输出尺寸（必须为偶数）
  --query STRING                附加到本地 HTML 的查询参数（不含 ?）

本机运行时：
  --playwright-module PATH      已安装的 playwright/playwright-core 路径
  --browser PATH                Chromium、Chrome 或 Edge 可执行文件
  --ffmpeg PATH                 ffmpeg 可执行文件，默认从环境查找
  --ffprobe PATH                ffprobe 可执行文件，默认从环境查找

页面必须提供 window.renderAt(t) 和 window.READY（Promise）。脚本禁止远程
HTTP/WebSocket 资源，不安装依赖，不添加音频、水印或角标。`;

function fail(message) { throw new Error(message); }
function parseNumber(name, value, { integer = false, positive = false } = {}) {
  const number = Number(value);
  if (!Number.isFinite(number) || (integer && !Number.isInteger(number)) || (positive && number <= 0)) fail(`--${name} 参数无效`);
  return number;
}

function parseArgs() {
  const args = process.argv.slice(2);
  if (!args.length || args.includes('--help') || args.includes('-h')) { console.log(HELP); process.exit(0); }
  const opt = { entry: path.resolve(args.shift()), fps: 60, width: 1920, height: 1080, start: 0 };
  const flags = new Set(['probe']);
  const values = new Set(['output', 'stills-dir', 'times', 'start', 'end', 'fps', 'width', 'height', 'query', 'playwright-module', 'browser', 'ffmpeg', 'ffprobe']);
  while (args.length) {
    const raw = args.shift();
    if (!raw.startsWith('--')) fail(`未知参数：${raw}`);
    const key = raw.slice(2);
    if (flags.has(key)) { opt[key] = true; continue; }
    if (!values.has(key) || !args.length) fail(`未知或缺少参数值：--${key}`);
    opt[key] = args.shift();
  }
  if (!fs.existsSync(opt.entry) || !fs.statSync(opt.entry).isFile() || path.extname(opt.entry).toLowerCase() !== '.html') fail('ENTRY 必须是本地 HTML 文件');
  opt.fps = parseNumber('fps', opt.fps, { integer: true, positive: true });
  opt.width = parseNumber('width', opt.width, { integer: true, positive: true });
  opt.height = parseNumber('height', opt.height, { integer: true, positive: true });
  opt.start = parseNumber('start', opt.start);
  if (opt.start < 0) fail('--start 不能小于 0');
  if (opt.end != null) opt.end = parseNumber('end', opt.end, { positive: true });
  const modes = [Boolean(opt.output), Boolean(opt['stills-dir']), Boolean(opt.probe)].filter(Boolean).length;
  if (modes !== 1) fail('必须且只能选择 --output、--stills-dir 或 --probe');
  if (opt.output) {
    opt.output = path.resolve(opt.output);
    if (path.extname(opt.output).toLowerCase() !== '.mp4') fail('--output 必须使用 .mp4 扩展名');
    if (opt.width % 2 || opt.height % 2) fail('H.264 yuv420p 要求 width/height 为偶数');
    if (fs.existsSync(opt.output)) fail(`拒绝覆盖已有文件：${opt.output}`);
    if (!fs.existsSync(path.dirname(opt.output))) fail('输出目录不存在');
  }
  if (opt['stills-dir']) {
    opt['stills-dir'] = path.resolve(opt['stills-dir']);
    if (fs.existsSync(opt['stills-dir'])) fail(`拒绝覆盖已有目录：${opt['stills-dir']}`);
    if (!fs.existsSync(path.dirname(opt['stills-dir']))) fail('预览帧父目录不存在');
    if (!opt.times) fail('--stills-dir 需要 --times');
    opt.times = opt.times.split(',').map(value => parseNumber('times', value));
    if (opt.times.some(value => value < 0)) fail('--times 不能包含负数');
  } else if (opt.times) fail('--times 仅可配合 --stills-dir');
  for (const key of ['browser', 'ffmpeg', 'ffprobe', 'playwright-module']) if (opt[key]) opt[key] = path.resolve(opt[key]);
  return opt;
}

function resolveExecutable(explicit, envNames, commands) {
  const requested = explicit || envNames.map(name => process.env[name]).find(Boolean);
  if (requested) {
    if (!fs.existsSync(requested) || !fs.statSync(requested).isFile()) fail(`可执行文件不存在：${requested}`);
    return requested;
  }
  for (const command of commands) {
    const result = spawnSync(command, ['-version'], { stdio: 'ignore' });
    if (!result.error && result.status === 0) return command;
  }
  fail(`找不到 ${commands[0]}，请显式传入路径`);
}

async function resolvePlaywright(opt) {
  const require = createRequire(import.meta.url);
  const candidates = [];
  if (opt['playwright-module']) candidates.push(opt['playwright-module']);
  for (const name of ['playwright-core', 'playwright']) {
    try { candidates.push(require.resolve(name)); } catch {}
  }
  for (let candidate of candidates) {
    if (!fs.existsSync(candidate)) continue;
    if (fs.statSync(candidate).isDirectory()) {
      const packageFile = path.join(candidate, 'package.json');
      if (!fs.existsSync(packageFile)) continue;
      const packageData = JSON.parse(fs.readFileSync(packageFile, 'utf8'));
      candidate = path.join(candidate, packageData.main || 'index.js');
    }
    const module = await import(pathToFileURL(candidate).href);
    const chromium = module.chromium || module.default?.chromium;
    if (chromium) return chromium;
  }
  fail('找不到现有 Playwright。请用 --playwright-module 指定 playwright-core/playwright');
}

function browserCandidates(explicit, chromium) {
  if (explicit) return [explicit];
  const roots = [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean);
  const paths = [
    process.env.XYCUT_BROWSER_PATH, process.env.CHROME, process.env.EDGE,
    ...roots.flatMap(root => [
      path.join(root, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      path.join(root, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    ]),
  ].filter(Boolean);
  try { paths.push(chromium.executablePath()); } catch {}
  return [...new Set(paths)];
}

function probe(ffprobe, file, countFrames = false) {
  const args = ['-v', 'error', ...(countFrames ? ['-count_frames'] : []), '-show_streams', '-show_format', '-of', 'json', file];
  const result = spawnSync(ffprobe, args, { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });
  if (result.error || result.status !== 0) fail(`ffprobe 失败：${result.error?.message || result.stderr}`);
  return JSON.parse(result.stdout);
}

async function main() {
  const opt = parseArgs();
  const chromium = await resolvePlaywright(opt);
  const browserPath = browserCandidates(opt.browser, chromium).find(candidate => candidate && fs.existsSync(candidate));
  if (!browserPath) fail('找不到 Chromium/Chrome/Edge，请用 --browser 指定');
  const ffmpeg = opt.output ? resolveExecutable(opt.ffmpeg, ['XYCUT_FFMPEG_PATH', 'FFMPEG_PATH'], ['ffmpeg', 'ffmpeg.exe']) : null;
  const ffprobe = opt.output ? resolveExecutable(opt.ffprobe, ['XYCUT_FFPROBE_PATH', 'FFPROBE_PATH'], ['ffprobe', 'ffprobe.exe']) : null;
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'xycut-motion-'));
  const errors = new Set();
  let browser, encoder, encoderDone;
  const check = () => { if (errors.size) fail([...errors].join('\n')); };
  try {
    browser = await chromium.launch({
      executablePath: browserPath,
      headless: true,
      args: ['--allow-file-access-from-files', '--force-color-profile=srgb', '--disable-background-timer-throttling', '--disable-renderer-backgrounding'],
    });
    const context = await browser.newContext({ viewport: { width: opt.width, height: opt.height }, deviceScaleFactor: 1, serviceWorkers: 'block' });
    await context.route('**/*', route => {
      const url = route.request().url();
      if (/^https?:/i.test(url)) { errors.add(`已阻止远程资源：${url}`); return route.abort(); }
      return route.continue();
    });
    if (context.routeWebSocket) await context.routeWebSocket('**/*', socket => { errors.add('已阻止 WebSocket'); socket.close(); });
    const page = await context.newPage();
    page.on('pageerror', error => errors.add(`页面脚本错误：${error.message}`));
    page.on('console', message => { if (message.type() === 'error') errors.add(`页面控制台错误：${message.text()}`); });
    page.on('requestfailed', request => {
      if (request.resourceType() === 'media' && request.failure()?.errorText === 'net::ERR_ABORTED') return;
      errors.add(`资源加载失败：${request.url()}（${request.failure()?.errorText || '未知错误'}）`);
    });
    const entryUrl = new URL(pathToFileURL(opt.entry).href);
    if (opt.query) entryUrl.search = opt.query;
    await page.goto(entryUrl.href, { waitUntil: 'load', timeout: 90000 });
    check();
    await page.waitForFunction(() => typeof window.renderAt === 'function' && (
      window.READY || window.__XYCUT_READY__ === true || document.title === 'XYCUT_READY'
    ), null, { timeout: 90000 });
    await page.evaluate(async () => {
      if (window.READY) {
        await Promise.race([
          Promise.resolve(window.READY),
          new Promise((_, reject) => setTimeout(() => reject(new Error('READY 等待超时')), 90000)),
        ]);
      }
    });
    check();

    const end = opt.end ?? await page.evaluate(() => Number(window.END ?? window.__XYCUT_DURATION__));
    if (!Number.isFinite(end) || end <= 0 || end <= opt.start) fail('结束时间无效，或没有晚于 start');
    const pageInfo = await page.evaluate(() => ({
      end: Number(window.END ?? window.__XYCUT_DURATION__),
      planCanvas: window.VISUAL_PLAN?.canvas || null,
      title: document.title,
    }));
    if (opt.probe) {
      console.log(JSON.stringify({ entry: opt.entry, end, fps: opt.fps, width: opt.width, height: opt.height, browser: browserPath, page: pageInfo }, null, 2));
      return;
    }

    async function prepareFrame(time) {
      await page.evaluate(async value => {
        await window.renderAt(value);
        if (window.VideoMedia?.settle) await window.VideoMedia.settle();
        await document.fonts.ready;
        const images = [...document.images].filter(image => {
          for (let node = image; node; node = node.parentElement) {
            const style = getComputedStyle(node);
            if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return false;
          }
          return Boolean(image.currentSrc || image.src);
        });
        for (const image of images) {
          if (!image.complete || !image.naturalWidth) throw new Error(`图片未就绪：${image.currentSrc || image.src}`);
          if (image.decode) await image.decode();
        }
        const videos = [...document.querySelectorAll('video')].filter(video => !video.closest('[hidden]'));
        for (const video of videos) {
          video.pause();
          if (video.readyState < 2) throw new Error(`视频帧未就绪：${video.currentSrc || video.src}`);
        }
      }, time);
      check();
    }

    if (opt['stills-dir']) {
      if (opt.times.some(time => time >= end)) fail('--times 中的时间必须小于 end');
      fs.mkdirSync(opt['stills-dir']);
      for (let index = 0; index < opt.times.length; index++) {
        const time = opt.times[index];
        await prepareFrame(time);
        const name = `frame_${String(index + 1).padStart(3, '0')}_${time.toFixed(3)}s.png`;
        await page.screenshot({ path: path.join(opt['stills-dir'], name), type: 'png' });
      }
      console.log(JSON.stringify({ output: opt['stills-dir'], times: opt.times, width: opt.width, height: opt.height }, null, 2));
      return;
    }

    const firstFrame = Math.round(opt.start * opt.fps);
    const lastFrame = Math.round(end * opt.fps);
    const frameCount = lastFrame - firstFrame;
    const duration = frameCount / opt.fps;
    if (frameCount <= 0) fail('输出不足一帧');
    const stagedOutput = path.join(temporary, 'output.mp4');
    const args = [
      '-n', '-hide_banner', '-loglevel', 'error',
      '-f', 'image2pipe', '-framerate', String(opt.fps), '-c:v', 'png', '-i', 'pipe:0',
      '-map', '0:v:0', '-map_metadata', '-1', '-an',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-pix_fmt', 'yuv420p',
      '-color_range', 'tv', '-colorspace', 'bt709', '-color_trc', 'bt709', '-color_primaries', 'bt709',
      '-frames:v', String(frameCount), '-t', String(duration), '-movflags', '+faststart', stagedOutput,
    ];
    encoder = spawn(ffmpeg, args, { stdio: ['pipe', 'ignore', 'pipe'] });
    let diagnostic = '', pipeError;
    encoder.stderr.on('data', chunk => { diagnostic = (diagnostic + chunk).slice(-8000); });
    encoder.stdin.on('error', error => { pipeError = error; });
    encoderDone = new Promise(resolve => {
      encoder.once('error', error => resolve({ error }));
      encoder.once('close', code => resolve({ code }));
    });
    for (let frame = firstFrame; frame < lastFrame; frame++) {
      if (pipeError || encoder.exitCode !== null) fail(`FFmpeg 提前停止：${pipeError?.message || diagnostic}`);
      await prepareFrame(frame / opt.fps);
      const png = await page.screenshot({ type: 'png' });
      await new Promise((resolve, reject) => encoder.stdin.write(png, error => error ? reject(error) : resolve()));
      if ((frame - firstFrame) % Math.max(1, opt.fps * 5) === 0) console.error(`已渲染 ${frame - firstFrame + 1}/${frameCount} 帧`);
    }
    encoder.stdin.end();
    const encoded = await encoderDone;
    if (encoded.error || encoded.code !== 0) fail(`FFmpeg 编码失败：${encoded.error?.message || diagnostic || encoded.code}`);
    const metadata = probe(ffprobe, stagedOutput, true);
    const video = metadata.streams.find(stream => stream.codec_type === 'video');
    const actualFrames = Number(video?.nb_read_frames);
    const actualDuration = Number(video?.duration || metadata.format?.duration);
    if (actualFrames !== frameCount) fail(`帧数校验失败：期望 ${frameCount}，实际 ${actualFrames}`);
    if (!Number.isFinite(actualDuration) || Math.abs(actualDuration - duration) > 1 / opt.fps + 0.001) fail('时长校验失败，误差超过一帧');
    if (metadata.streams.some(stream => stream.codec_type === 'audio')) fail('输出不应包含音频轨道');
    fs.copyFileSync(stagedOutput, opt.output, fs.constants.COPYFILE_EXCL);
    console.log(JSON.stringify({ output: opt.output, frames: frameCount, fps: opt.fps, duration, width: opt.width, height: opt.height, codec: video.codec_name, audio: false }, null, 2));
  } finally {
    if (encoder && encoder.exitCode === null) encoder.kill();
    if (browser) await browser.close();
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

main().catch(error => {
  console.error(`渲染失败：${error.stack || error.message}`);
  process.exitCode = 1;
});
