"""Generate a Tester-only scheduler experiment; canonical src and sets stay intact."""
import argparse
from pathlib import Path
import tempfile

try:
    from .build_tester_mc_timeline import build as base_build
    from .build_tester_pipeline import SOURCE, MAIN, STATE, replace_once
except ImportError:
    from build_tester_mc_timeline import build as base_build
    from build_tester_pipeline import SOURCE, MAIN, STATE, replace_once

TOOLS=Path(__file__).resolve().parent
CAPS=(20000,200000,500000,1000000)


def scheduling_core(text, mode):
    if mode not in range(6):raise ValueError('unsupported scheduler')
    if text.count('operations<20000')!=1:raise ValueError('MC chunk guard changed or ambiguous')
    if mode<4:
        return text.replace('operations<20000',f'operations<{CAPS[mode]}')
    text=text.replace(' int operations=0;',f' int operations=0;ulong sliceEnd=GetMicrosecondCount()+{5000 if mode==4 else 10000};')
    return text.replace('operations<20000','GetMicrosecondCount()<sliceEnd')


def replay_core(source):
    start=source.index('uint NextMCRandom()')
    end=source.index('\nbool InUniverseNow()',start)
    text=source[start:end]
    rng=text[:text.index('void AdvanceMonteCarlo(')]
    original=text[text.index('void AdvanceMonteCarlo('):]
    original=original.replace('  if(dd<=MonteCarloMaxDrawdownPercent*MonteCarloSafetyFactor || m_mcCandidate==0)',
                              '  Level(dd);\n  if(dd<=MonteCarloMaxDrawdownPercent*MonteCarloSafetyFactor || m_mcCandidate==0)')
    original=original.replace('   PrintFormat("MC %s: samples=%d winrate=%.2f%% cap=%.4f%%",m_symbol,g_sampleCount,100*g_winRate,g_mcRisk);',
                              '   lastOperations=operations;')
    original=original.rstrip()[:-1]+' lastOperations=operations;\n}\n'
    return rng+'\n'.join(scheduling_core(original,i).replace('void AdvanceMonteCarlo(',f'void Advance{i}(') for i in range(6))


def build(output, mode=0, qualified=False):
    if mode not in range(6):raise ValueError('unsupported scheduler')
    output=Path(output).resolve()
    if output==SOURCE.resolve() or SOURCE.resolve() in output.parents or output.exists():
        raise ValueError('Output must be new and outside product src')
    with tempfile.TemporaryDirectory() as td:
        staged=Path(td)/'base';base_build(staged)
        files={p.name:p.read_bytes() for p in staged.iterdir()}
    tag=f'CodexMCSched{mode}_20260927'
    for name in ('TesterMCTimelineDiag.mqh','TesterBottleneckDiag.mqh','TesterOpportunityDiag.mqh'):
        files[name]=files[name].replace(b'CodexMCTimeline_20260927',tag.encode()).replace(
            b'CodexMCTimelineDetail_20260927',(tag+'Detail').encode()).replace(
            b'CodexMCTimelineLegacy_20260927',(tag+'Legacy').encode())
    files['TesterMCTimelineDiag.mqh']+=b'\n#include "TesterMCSchedulerDiag.mqh"\n'
    header=(TOOLS/'TesterMCSchedulerDiag.mqh').read_bytes()
    files['TesterMCSchedulerDiag.mqh']=f'#define MCS_MODE {mode}\n'.encode()+header
    files['TesterMCSchedulerCore.mqh']=replay_core((SOURCE/STATE).read_text(encoding='utf-8-sig')).encode()
    main=files[MAIN]
    main=replace_once(main,' g_tpmcTimer++;',' g_tpmcTimer++;ulong mcsTimerStart=GetMicrosecondCount();')
    main=replace_once(main,' DispatchQueue();ServiceTradeJournals();RenderDashboard();',
                     ' DispatchQueue();ServiceTradeJournals();RenderDashboard();\n MCSMeasure(1,GetMicrosecondCount()-mcsTimerStart);')
    text=main.decode()
    tick_start=text.index('void OnTick()');tick_end=text.index('\nvoid OnTradeTransaction(',tick_start)
    tick=text[tick_start:tick_end]
    measured=tick.replace('{','{ulong mcsTickStart=GetMicrosecondCount();',1)
    closing=measured.rindex('}')
    measured=measured[:closing]+'MCSMeasure(0,GetMicrosecondCount()-mcsTickStart);'+measured[closing:]
    main=main.replace(tick.encode(),measured.encode(),1)
    main+=b'\ndouble OnTester() {MCSFinish();return 0;}\n'
    files[MAIN]=main
    methods=files['TesterMCTimelineMethods.mqh']
    methods=replace_once(methods,'  m_tpmcAdvanceUs+=GetMicrosecondCount()-start;m_tpmcOperations+=(ulong)m_tpmcLastOperations;m_tpmcCalls++;',
       '  ulong elapsed=GetMicrosecondCount()-start;\n  m_tpmcAdvanceUs+=elapsed;m_tpmcOperations+=(ulong)m_tpmcLastOperations;m_tpmcCalls++;\n  MCSActualCallback(m_tpmcCycle,m_tpmcLastOperations,elapsed);')
    methods=replace_once(methods,' TPMCEmit("COMPLETE",reason);',
       ' if(reason=="BOOTSTRAP_ALLOWED" || reason=="BOOTSTRAP_DENIED") MCSActualComplete(m_tpmcCycle,g_mcRisk,g_mcAllowed,m_mcRandom,m_mcCandidate);\n TPMCEmit("COMPLETE",reason);')
    files['TesterMCTimelineMethods.mqh']=methods
    state=files[STATE]
    state=replace_once(state,'m_tpbMCStarted=TimeCurrent();TPMCEmit("START");',
        'm_tpbMCStarted=TimeCurrent();TPMCEmit("START");MCSCapture(m_tpmcCycle,m_mcReturns,m_tpmcDigest);')
    state=replace_once(state,'  m_tpbLastDD=dd;m_tpbDDSeen=true;',
        '  m_tpbLastDD=dd;m_tpbDDSeen=true;MCSActualLevel(m_tpmcCycle,m_mcCandidate,dd,m_mcRandom);')
    start=state.index(b'void AdvanceMonteCarloCore(');end=state.index(b'\nbool InUniverseNow()',start)
    core=state[start:end].decode();core=scheduling_core(core,mode)
    state=state[:start]+core.encode()+state[end:]
    files[STATE]=state
    if qualified:
        # The multi-symbol Tester builder completes the matching header/schema
        # transform. Existing single-symbol generator output stays byte-identical.
        methods=files['TesterMCTimelineMethods.mqh']
        methods=replace_once(methods,
            'MCSActualCallback(m_tpmcCycle,m_tpmcLastOperations,elapsed);',
            'MCSActualCallback(m_symbol,"ACTUAL",m_tpmcCycle,m_tpmcLastOperations,start,GetMicrosecondCount(),m_tpmcInputVersion,m_tpmcHistoryVersion);')
        methods=replace_once(methods,
            'MCSActualComplete(m_tpmcCycle,g_mcRisk,g_mcAllowed,m_mcRandom,m_mcCandidate);',
            'MCSActualComplete(m_symbol,"ACTUAL",m_tpmcCycle,g_mcRisk,g_mcAllowed,m_mcRandom,m_mcCandidate);')
        files['TesterMCTimelineMethods.mqh']=methods
        state=files[STATE]
        state=replace_once(state,'MCSCapture(m_tpmcCycle,m_mcReturns,m_tpmcDigest);',
            'MCSCapture(m_symbol,"ACTUAL",m_tpmcCycle,m_mcReturns,m_tpmcDigest,m_tpmcInputVersion,m_tpmcHistoryVersion);')
        state=replace_once(state,'MCSActualLevel(m_tpmcCycle,m_mcCandidate,dd,m_mcRandom);',
            'MCSActualLevel(m_symbol,"ACTUAL",m_tpmcCycle,m_mcCandidate,dd,m_mcRandom);')
        files[STATE]=state
    output.mkdir(parents=True)
    for name,data in files.items():(output/name).write_bytes(data)
    return output/MAIN


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',type=int,default=0)
    a=p.parse_args();print(build(a.output,a.mode))
