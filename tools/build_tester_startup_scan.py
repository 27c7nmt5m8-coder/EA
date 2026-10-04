"""Reversible first-100 nested startup probes in Tester-only copied sources."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from tools.build_tester_journal_io import build as baseline_build
from tools.build_tester_pipeline import MAIN, STATE, replace_once

SECTIONS={'timer','initialization','scan','maintain','lines','horizontal_lines','trend_lines',
          'candidate','preflight','observer','analyze_all','analyze_tf','handle_access',
          'patterns','gather_patterns','history','initial_risks','force_mc','position',
          'series_bars','series_close','series_time','copy_buffer','create_atr','create_ema','create_adx','create_macd',
          'pattern_double_bottom','pattern_double_top','pattern_inverse_hs','pattern_hs','pattern_triple','pattern_123','pattern_failed_breakout'}


class SafeDiagnosticParser(argparse.ArgumentParser):
    def error(self,message):
        # argparse's default error text embeds the rejected argument value.
        raise ValueError('invalid diagnostic CLI arguments')


def wrapper(name,kind,params,args,stage,tf='0',observer='g_tpShadow',handle=False):
    signature=f'{kind} {name}({params})'
    old=signature+'\n'
    before=' int scBefore=ArraySize(g_indicators);\n' if handle else ''
    call=(' '+kind+' scValue=' if kind!='void' else ' ')+f'SCCore{name}({args});\n'
    after=' SCLeave(scSpan,ArraySize(g_indicators)>scBefore?1:0,scValue!=INVALID_HANDLE?1:0);\n' if handle else ' SCLeave(scSpan);\n'
    returned=' return scValue;\n' if kind!='void' else ''
    new=(signature+'\n{\n'+f' int scSpan=SCEnter(m_symbol,"{stage}",{observer},(int){tf});\n'+
         before+call+after+returned+'}\n'+f'{kind} SCCore{name}({params})\n')
    return old,new


def edits_for(name):
    if name==MAIN:return (
        ('#include "MT3SymbolState.mqh"','#include "TesterStartupScanDiag.mqh"\n#include "MT3SymbolState.mqh"'),
        ('TLBegin(mcsTimerStart);','TLBegin(mcsTimerStart);SCBegin(g_tpmcTimer,mcsTimerStart);'),
        ('MCSMeasure(1,tlEnd-mcsTimerStart);','SCFinish(tlEnd);MCSMeasure(1,tlEnd-mcsTimerStart);'),
        ('TLExport();TJExport();','SCExport();TLExport();TJExport();'),
        ('int OnInit()\n','int OnInit()\n{\n ulong scStart=GetMicrosecondCount();SCBegin(0,scStart);int scValue=SCCoreOnInit();SCFinish(GetMicrosecondCount());return scValue;\n}\nint SCCoreOnInit()\n'),
    )
    if name==STATE:
        definitions=[('Scan','void','','','scan'),('Maintain','void','bool updateStats','updateStats','maintain'),
          ('UpdateAllAutoLines','void','','','lines'),('UpdateAutoHorizontalLines','void','','','horizontal_lines'),
          ('UpdateAutoTrendLines','void','','','trend_lines'),('RefreshCandidate','bool','','','candidate'),
          ('EntryPreflight','bool','bool manual','manual','preflight'),
          ('AnalyzeAllTimeframes','bool','MTFResult &results[]','results','analyze_all'),
          ('AnalyzeTimeframe','bool','ENUM_TIMEFRAMES timeframe,MTFResult &result','timeframe,result','analyze_tf'),
          ('CachedIndicator','int','int kind,ENUM_TIMEFRAMES tf,int period','kind,tf,period','handle_access'),
          ('RefreshHistory','void','','','history'),('CaptureInitialRisks','void','','','initial_risks'),
          ('UpdateMonteCarloRisk','void','bool force=false,int tpmcPath=0','force,tpmcPath','force_mc'),('ManagePositions','void','','','position'),
          ('DetectDoubleBottom','bool','PatternSignal &signal','signal','pattern_double_bottom'),
          ('DetectDoubleTop','bool','PatternSignal &signal','signal','pattern_double_top'),
          ('DetectInverseHeadShoulders','bool','PatternSignal &signal','signal','pattern_inverse_hs'),
          ('DetectHeadShoulders','bool','PatternSignal &signal','signal','pattern_hs'),
          ('DetectTriplePattern','bool','bool bottom,PatternSignal &signal','bottom,signal','pattern_triple')]
        pairs=[]
        for function,kind,params,args,section in definitions:
            tf='timeframe' if function=='AnalyzeTimeframe' else 'tf' if function=='CachedIndicator' else '0'
            pair=wrapper(function,kind,params,args,section,tf,handle=function=='CachedIndicator')
            # Existing line-update declarations place their opening brace at two-space indentation.
            pairs.append(pair)
        pairs.extend((('int tpBars=Bars(m_symbol,timeframe);','int tpBars=SCBars(m_symbol,timeframe);'),
                      ('Bars(m_symbol,tf)','SCBars(m_symbol,tf)'),
                      ('result.close=iClose(m_symbol,timeframe,1);','result.close=SCClose(m_symbol,timeframe,1);'),
                      (' int copied=CopyBuffer(handle,buffer,shift,1,a);int tlCopyError=GetLastError();',
                       ' int scCopy=SCEnter(m_symbol,"copy_buffer",g_tpShadow);\n int copied=CopyBuffer(handle,buffer,shift,1,a);int tlCopyError=GetLastError();SCLeave(scCopy,buffer,copied);')))
        for statement in ('datetime line=iTime(m_symbol,LineTimeframe,0);',
                          'g_lastBarTime=iTime(m_symbol,PERIOD_M1,0);',
                          'ENUM_TIMEFRAMES tf=MT3Timeframe(i);datetime bar=iTime(m_symbol,tf,0);',
                          'result.bar=iTime(m_symbol,timeframe,0);if(result.bar<=0)',
                          'if(result.bar!=iTime(m_symbol,timeframe,0))'):
            pairs.append((statement,statement.replace('iTime(', 'SCTime(')))
        pairs.extend((('h=iATR(m_symbol,tf,period);','h=SCATR(m_symbol,tf,period);'),
                      ('h=iMA(m_symbol,tf,period,0,MODE_EMA,PRICE_CLOSE);','h=SCMA(m_symbol,tf,period);'),
                      ('h=iADX(m_symbol,tf,period);','h=SCADX(m_symbol,tf,period);'),
                      ('h=iMACD(m_symbol,tf,fast,slow,signal,PRICE_CLOSE);','h=SCMACD(m_symbol,tf,fast,slow,signal);')))
        return tuple(pairs)
    if name=='TesterOpportunityMethods.mqh':return (wrapper('TPObserveBeforeSafety','void','const bool allowed,const int reason','allowed,reason','observer',observer='true'),)
    if name=='MT3ReversalPatterns.mqh':return (
        wrapper('SelectReversalPattern','bool','MTFResult &r[],PatternSignal &signal','r,signal','patterns'),
        wrapper('GatherPatterns','bool','PatternSignal &candidates[]','candidates','gather_patterns'),
        wrapper('Detect123Reversal','bool','bool buy,PatternSignal &signal','buy,signal','pattern_123'),
        wrapper('DetectFailedBreakout','bool','bool buy,PatternSignal &signal','buy,signal','pattern_failed_breakout'))
    return ()


def restore_file(name,data):
    for old,new in reversed(edits_for(name)):data=replace_once(data,new,old)
    return data


def build(output,mode=2):
    main=baseline_build(Path(output),mode)
    for name in (MAIN,STATE,'TesterOpportunityMethods.mqh','MT3ReversalPatterns.mqh'):
        p=main.parent/name;original=p.read_bytes();data=original
        for old,new in edits_for(name):data=replace_once(data,old,new)
        if restore_file(name,data)!=original:raise ValueError('startup probe is not reversible')
        p.write_bytes(data)
    (main.parent/'TesterStartupScanDiag.mqh').write_bytes(Path(__file__).with_name('TesterStartupScanDiag.mqh').read_bytes())
    return main


def analyze_spans(rows):
    spans={};children=defaultdict(list);exclusive=defaultdict(int);roots=[]
    required={'span_id','parent_id','timer_id','server_s','symbol','context','section','start_wall_us','end_wall_us','duration_us','timeframe','detail','result'}
    for row in rows:
        if set(row)!=required or row['section'] not in SECTIONS or row['context'] not in ('ACTUAL','OBSERVER') or row['symbol'] not in ('ALL','USDJPY','EURUSD','EURJPY','XAUUSD'):raise ValueError('unknown span schema/value')
        try:r={k:int(v) for k,v in row.items() if k not in ('symbol','context','section')}
        except (ValueError,TypeError):raise ValueError('unparseable timing') from None
        i=r['span_id'];r.update({k:row[k] for k in ('symbol','context','section')})
        if i in spans or i<=0 or r['parent_id']>=i or min(r['parent_id'],r['timer_id'],r['start_wall_us'])<0 or r['timer_id']>100 or r['end_wall_us']-r['start_wall_us']!=r['duration_us'] or r['duration_us']<0:raise ValueError('invalid span identity/clock')
        spans[i]=r
        if r['parent_id']:children[r['parent_id']].append(r)
        elif r['section'] in ('timer','initialization') and r['symbol']=='ALL':roots.append(r)
        else:raise ValueError('invalid root')
    if not roots:raise ValueError('missing bounded probe roots')
    if len({r['timer_id'] for r in roots})!=len(roots):raise ValueError('duplicate timer root')
    for i,r in spans.items():
        if r['parent_id']:
            if r['parent_id'] not in spans:raise ValueError('missing parent')
            p=spans[r['parent_id']]
            if r['timer_id']!=p['timer_id'] or r['server_s']!=p['server_s'] or not p['start_wall_us']<=r['start_wall_us']<=r['end_wall_us']<=p['end_wall_us']:raise ValueError('mixed/outside parent')
            if p['symbol']!='ALL' and r['symbol']!=p['symbol']:raise ValueError('mixed symbol subtree')
        siblings=sorted(children[i],key=lambda x:x['start_wall_us'])
        if any(a['end_wall_us']>b['start_wall_us'] for a,b in zip(siblings,siblings[1:])):raise ValueError('overlapping siblings')
        cost=r['duration_us']-sum(c['duration_us'] for c in siblings)
        if cost<0:raise ValueError('negative residual')
        exclusive[r['section']]+=cost
    return dict(timer_count=sum(r['section']=='timer' for r in roots),span_count=len(spans),exclusive_us=dict(exclusive),roots=roots,spans=list(spans.values()),queue_wait='UNKNOWN',os_scheduling='UNKNOWN')


if __name__=='__main__':
    p=SafeDiagnosticParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--mode',type=int,choices=(0,2),default=2)
    try:
        a=p.parse_args();build(a.output,a.mode)
    except Exception as e:print(json.dumps(dict(status='BLOCKED',exception=type(e).__name__)));raise SystemExit(1) from None
