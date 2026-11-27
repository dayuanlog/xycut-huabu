"""按最终字词时间平滑避让配音，独立混合配音、音效和用户提供的BGM。"""
from pathlib import Path
import argparse
import json
import math
import re
import shutil
import subprocess


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')


def speech_regions(timeline, pause, attack=.18, hold=.25, release=.8, offset=0):
    if not math.isfinite(offset) or offset < 0:
        raise ValueError('正文时间偏移必须为非负有限秒数')
    ranges=[]
    for line in timeline['lines']:
        for token in line.get('tokens') or [line]:
            ranges.append((token['target_start_ms']/1000+offset,token['target_end_ms']/1000+offset))
    merged=[]
    for start,end in sorted(ranges):
        if merged and start-merged[-1][1] <= max(pause,attack+hold+release):
            merged[-1][1]=max(merged[-1][1],end)
        else:
            merged.append([start,end])
    return merged


def gain_points(regions, duration, duck, opened, attack=.18, hold=.25, release=.8):
    points={0.0:opened,duration:opened}
    for start,end in regions:
        if start>=duration:
            continue
        if start<attack:
            points[0.0]=duck
        else:
            points[max(0,start-attack)]=opened
            points[start]=duck
        points[min(duration,end+hold)]=duck
        if end+hold<duration:
            points[min(duration,end+hold+release)]=opened
    return sorted(points.items())


def volume_expression(points):
    expr=f'{points[-1][1]:.6f}'
    for (a,ga),(b,gb) in reversed(list(zip(points,points[1:]))):
        value=f'{ga:.6f}' if ga==gb else f'({ga:.6f}+({gb-ga:.6f})*(t-{a:.6f})/{b-a:.6f})'
        expr=f'if(lt(t,{b:.6f}),{value},{expr})'
    return 'pow(10,('+expr+')/20)'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--music',type=Path,required=True)
    parser.add_argument('--voice',type=Path,required=True)
    parser.add_argument('--timeline',type=Path,required=True)
    parser.add_argument('--ffmpeg',type=Path,required=True)
    parser.add_argument('--ffprobe',type=Path,required=True)
    parser.add_argument('--start',type=float,default=0)
    parser.add_argument('--duck-db',type=float,default=-7)
    parser.add_argument('--open-db',type=float,default=0)
    parser.add_argument('--min-pause',type=float,default=1.2)
    parser.add_argument('--timeline-offset',type=float,default=None,help='原ASR到最终播放时间的偏移；默认读取plan.intro.duration，已偏移的ASR可传0')
    args=parser.parse_args()
    project=args.project.resolve();assets=project/'assets'
    plan=read(project/'canvas-plan.json');timeline=read(args.timeline)
    intro=plan.get('intro') or {}
    if not isinstance(intro,dict):
        parser.error('plan.intro必须为对象')
    offset=args.timeline_offset if args.timeline_offset is not None else intro.get('duration',0)
    if isinstance(offset,bool) or not isinstance(offset,(int,float)) or not math.isfinite(offset) or offset<0:
        parser.error('正文时间偏移必须为非负有限秒数')
    if plan['timeline_revision']!=timeline['timeline_revision']:
        parser.error('画布与最终时间轴版本不一致')
    if args.start<0 or args.min_pause<0 or args.duck_db>args.open_db:
        parser.error('起点和停顿不能为负，人声段增益不能高于无人声段')
    length=plan['duration']
    info=json.loads(subprocess.check_output([str(args.ffprobe),'-v','error','-show_entries','format=duration','-of','json',str(args.music)]))
    music_duration=float(info['format']['duration'])
    if music_duration-args.start<length:
        parser.error('音乐选段不足全片时长，请提供更长音乐或先制作平滑衔接的音乐段')
    if not (assets/'sfx-track.wav').is_file():
        parser.error('缺少独立音效轨assets/sfx-track.wav，不能从已有混音中再次叠加配音')
    def run(values):
        result=subprocess.run([str(args.ffmpeg),'-hide_banner',*map(str,values)],capture_output=True,text=True,encoding='utf-8',errors='replace')
        if result.returncode:
            raise RuntimeError(result.stderr[-2200:])
        return result.stderr
    def levels(file, start=0, duration=None):
        out=run(['-ss',start,'-i',file,*(['-t',duration] if duration else []),'-af','volumedetect','-f','null','-'])
        return {key:float(re.search(key+r'_volume:\s*(-?[\d.]+) dB',out).group(1)) for key in ['mean','max']}
    music_source=assets/'music'/('bgm-source'+args.music.suffix.lower());music_source.parent.mkdir(parents=True,exist_ok=True)
    if args.music.resolve()!=music_source.resolve():
        shutil.copy2(args.music,music_source)
    no_music=assets/'preview-no-bgm.mp3'
    if not no_music.exists() and (assets/'preview-mix.mp3').exists():
        shutil.copy2(assets/'preview-mix.mp3',no_music)
    regions=speech_regions(timeline,args.min_pause,offset=offset)
    points=gain_points(regions,length,args.duck_db,args.open_db)
    expression=volume_expression(points)
    bed=assets/'bgm-track.wav'
    fade_in=min(.8,length/3);fade_out=min(.9,length/3)
    # 音乐单独规整动态后避让；音乐限峰低于片尾的主要音效，不改变人声或音效增益。
    music_filter=f"atrim=0:{length},asetpts=PTS-STARTPTS,loudnorm=I=-22:TP=-2:LRA=9,aresample=48000,aformat=channel_layouts=stereo,volume='{expression}':eval=frame,afade=t=in:st=0:d={fade_in},afade=t=out:st={length-fade_out}:d={fade_out},alimiter=limit=0.2511886:level=0"
    run(['-y','-ss',args.start,'-i',music_source,'-af',music_filter,'-t',length,'-ar',48000,'-ac',2,'-c:a','pcm_s16le',bed])
    mixed=assets/'preview-mix.mp3'
    filters=f'[0:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={length}[v];[v][1:a][2:a]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.870964:level=0[mix]'
    run(['-y','-i',args.voice,'-i',assets/'sfx-track.wav','-i',bed,'-filter_complex',filters,'-map','[mix]','-t',length,'-ar',48000,'-ac',2,'-c:a','libmp3lame','-b:a','192k',mixed])
    tail_start=offset+plan.get('unvoiced_tail',{}).get('start',timeline['duration_ms']/1000)
    voiced_sample=levels(bed,regions[0][0],min(8,regions[0][1]-regions[0][0])) if regions else None
    report={'asset':music_source.relative_to(project).as_posix(),'source_duration':music_duration,'source_start':args.start,
            'duration':length,'timeline_offset':offset,'stem':'assets/bgm-track.wav','duck_db':args.duck_db,'open_db':args.open_db,
            'minimum_pause':args.min_pause,'attack':.18,'hold':.25,'release':.8,'fade_in':fade_in,'fade_out':fade_out,
            'normalization':'loudnorm I=-22 TP=-2 LRA=9; music peak ceiling -12dBFS',
            'speech_regions':regions,'gain_points':[{'time':t,'gain_db':g} for t,g in points],
            'stem_levels_dbfs':levels(bed),'voiced_sample_levels_dbfs':voiced_sample,
            'tail_sample_levels_dbfs':levels(bed,tail_start,length-tail_start) if length>tail_start else None}
    mix_levels=levels(mixed)
    if report['stem_levels_dbfs']['max'] < -70:
        raise RuntimeError('背景音乐近似静音，请检查音乐选段或增益')
    if mix_levels['max']>=0:
        raise RuntimeError('混音削波，需要调整背景音乐总线')
    cues=read(project/'audio-cues.json')
    cues.update(music=report,mixed_levels_dbfs=mix_levels,policy='保留原配音与已确认增强音效，加入用户BGM；按最终字词时间合并短停顿，音乐在人声下压低，长停顿与无配音片尾平滑抬高，首尾淡入淡出。')
    write(project/'audio-cues.json',cues)
    write(project/'audio-mix-report.json',{'music':report,'mixed_levels_dbfs':mix_levels,'voice_gain_db':0,'sfx_gain_db':0})
    print(json.dumps({'ok':True,'music_duration':music_duration,'speech_regions':regions,'gain_points':report['gain_points'],'music_levels':report['stem_levels_dbfs'],'mix_levels':mix_levels},ensure_ascii=False))


if __name__=='__main__':
    main()
