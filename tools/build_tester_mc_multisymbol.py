"""Build a source-linked, Tester-only multi-symbol MC contention variant."""
import argparse
import hashlib
from pathlib import Path
import tempfile

try:
    from .build_tester_mc_validation import build as validation_build
    from .build_tester_pipeline import SOURCE, MAIN, STATE, replace_once
except ImportError:
    from build_tester_mc_validation import build as validation_build
    from build_tester_pipeline import SOURCE, MAIN, STATE, replace_once

TOOLS = Path(__file__).resolve().parent
SOURCE_STATE_SHA256 = '63884c4949b5b134adcd631f8134db3da4ed2ddabd43cd5e6cf5e8d8af622ca4'


def change(text, old, new):
    return replace_once(text.encode(), old, new).decode()


def qualify_scheduler(text):
    """Namespace every snapshot/callback/replay record by symbol and kind."""
    text = change(text, ' int cycle,offset,count,candidate;long requested;bool completed,allowed;',
        ' int cycle,offset,count,candidate,inputVersion,historyVersion;long requested,serverEnd;bool completed,allowed;\n string symbol,kind;ulong wallStart,wallEnd,lastCallbackEnd;')
    text = change(text, 'struct MCSCallback {int cycle,operations;long server;ulong timer,elapsed;};',
        'struct MCSCallback {string symbol,kind;int cycle,operations,inputVersion,historyVersion;long server;ulong timer,id,start,end,elapsed,gap;bool gapKnown;};')
    text = change(text, 'int g_mcsUnknown=0;', 'int g_mcsUnknown=0,g_mcsMismatches=0,g_mcsComparisons=0;const int MCS_RECORD_LIMIT=3000000;const int MCS_INPUT_LIMIT=10000000;')
    text = change(text, 'if(ArrayResize(g_mcsTickUs,n+1,8192)==n+1)', 'if(n<MCS_RECORD_LIMIT && ArrayResize(g_mcsTickUs,n+1,8192)==n+1)')
    text = change(text, 'if(ArrayResize(g_mcsTimerUs,n+1,8192)==n+1)', 'if(n<MCS_RECORD_LIMIT && ArrayResize(g_mcsTimerUs,n+1,8192)==n+1)')
    text = change(text, 'int MCSFind(const int cycle)\n{for(int i=ArraySize(g_mcsSnapshots)-1;i>=0;i--) if(g_mcsSnapshots[i].cycle==cycle) return i;return -1;}',
        'int MCSFind(const string symbol,const string kind,const int cycle)\n{for(int i=ArraySize(g_mcsSnapshots)-1;i>=0;i--) if(g_mcsSnapshots[i].symbol==symbol && g_mcsSnapshots[i].kind==kind && g_mcsSnapshots[i].cycle==cycle) return i;return -1;}')
    text = change(text, 'void MCSCapture(const int cycle,double &returnsData[],const string digest)',
        'void MCSCapture(const string symbol,const string kind,const int cycle,double &returnsData[],const string digest,const int inputVersion,const int historyVersion)')
    text = change(text, 'if(count<=0 || MCSFind(cycle)>=0 || ArrayResize(g_mcsInput,offset+count)!=offset+count ||',
        'if(symbol=="" || (kind!="ACTUAL" && kind!="SHADOW" && kind!="SELFTEST") || count<=0 || n>=MCS_RECORD_LIMIT || offset+count>MCS_INPUT_LIMIT || MCSFind(symbol,kind,cycle)>=0 || ArrayResize(g_mcsInput,offset+count)!=offset+count ||')
    text = change(text, 's.cycle=cycle;s.offset=offset;s.count=count;s.requested=(long)TimeCurrent();s.inputDigest=digest;',
        's.symbol=symbol;s.kind=kind;s.cycle=cycle;s.offset=offset;s.count=count;s.requested=(long)TimeCurrent();s.wallStart=GetMicrosecondCount();s.inputDigest=digest;s.inputVersion=inputVersion;s.historyVersion=historyVersion;')
    text = change(text, 'void MCSActualLevel(const int cycle,const int candidate,const double dd,const uint rng)\n{int i=MCSFind(cycle);',
        'void MCSActualLevel(const string symbol,const string kind,const int cycle,const int candidate,const double dd,const uint rng)\n{int i=MCSFind(symbol,kind,cycle);')
    text = change(text, 'void MCSActualComplete(const int cycle,const double risk,const bool allowed,const uint rng,const int candidate)',
        'void MCSActualComplete(const string symbol,const string kind,const int cycle,const double risk,const bool allowed,const uint rng,const int candidate)')
    text = change(text, 'int i=MCSFind(cycle);if(i<0) {g_mcsUnknown++;return;}\n g_mcsSnapshots[i].completed=true;',
        'int i=MCSFind(symbol,kind,cycle);if(i<0) {g_mcsUnknown++;return;}\n g_mcsSnapshots[i].completed=true;g_mcsSnapshots[i].wallEnd=GetMicrosecondCount();g_mcsSnapshots[i].serverEnd=(long)TimeCurrent();')
    start = text.index('void MCSActualCallback(')
    end = text.index('\ndouble MCSQuantile(', start)
    text = text[:start] + '''void MCSActualCallback(const string symbol,const string kind,const int cycle,const int operations,
                       const ulong start,const ulong finish,const int inputVersion,const int historyVersion)
{
 int i=MCSFind(symbol,kind,cycle),n=ArraySize(g_mcsCallbacks);
 if(i<0 || operations<0 || finish<start || n>=MCS_RECORD_LIMIT || ArrayResize(g_mcsCallbacks,n+1,4096)!=n+1) {g_mcsUnknown++;return;}
 MCSSnapshot s=g_mcsSnapshots[i];
 MCSCallback c;ZeroMemory(c);c.symbol=symbol;c.kind=kind;c.cycle=cycle;c.operations=operations;
 c.inputVersion=inputVersion;c.historyVersion=historyVersion;c.server=(long)TimeCurrent();c.timer=g_tpmcTimer;c.id=(ulong)n+1;
 c.start=start;c.end=finish;c.elapsed=finish-start;c.gapKnown=s.lastCallbackEnd>0 && start>=s.lastCallbackEnd;
 if(c.gapKnown) c.gap=start-s.lastCallbackEnd;
 g_mcsCallbacks[n]=c;g_mcsSnapshots[i].lastCallbackEnd=finish;g_mcsSnapshots[i].operations+=(ulong)operations;
}
''' + text[end:]
    text = change(text, 'if(!FileWrite(h,"cycle","server_s","timer","operations","elapsed_us"))',
        'if(!FileWrite(h,"symbol","kind","cycle","callback_id","server_s","timer","start_wall_us","end_wall_us","elapsed_us","operations","input_version","history_version","service_gap_us","service_gap_known"))')
    text = change(text, 'if(!FileWrite(h,c.cycle,c.server,c.timer,c.operations,c.elapsed))',
        'if(!FileWrite(h,c.symbol,c.kind,c.cycle,c.id,c.server,c.timer,c.start,c.end,c.elapsed,c.operations,c.inputVersion,c.historyVersion,c.gapKnown?IntegerToString((long)c.gap):"UNKNOWN",(int)c.gapKnown))')
    text = change(text, 'h=MCSOpen("_events");if(h==INVALID_HANDLE) return;', '''h=MCSOpen("_snapshots");if(h==INVALID_HANDLE) return;
 if(!FileWrite(h,"symbol","kind","cycle","server_start_s","server_end_s","start_wall_us","end_wall_us","duration_us","samples","input_digest","input_version","history_version","completed","operations","risk_bits","allowed","rng","candidate")) g_mcsUnknown++;
 for(int i=0;i<ArraySize(g_mcsSnapshots);i++)
 {MCSSnapshot s=g_mcsSnapshots[i];if(!FileWrite(h,s.symbol,s.kind,s.cycle,s.requested,s.serverEnd,s.wallStart,s.wallEnd,s.completed?s.wallEnd-s.wallStart:0,s.count,s.inputDigest,s.inputVersion,s.historyVersion,(int)s.completed,s.operations,StringFormat("%I64X",s.riskBits),(int)s.allowed,s.rng,s.candidate)) g_mcsUnknown++;}
 FileFlush(h);FileClose(h);
 h=MCSOpen("_events");if(h==INVALID_HANDLE) return;''')
    text = change(text, 'if(!FileWrite(h,"event","count","total_us"', 'if(!FileWrite(h,"symbol","kind","cycle","event","count","total_us"')
    text = change(text, 'if(!FileWrite(h,"OnTick",ArraySize(g_mcsTickUs)', 'if(!FileWrite(h,_Symbol,"GLOBAL",0,"OnTick",ArraySize(g_mcsTickUs)')
    text = change(text, 'if(!FileWrite(h,"OnTimer",ArraySize(g_mcsTimerUs)', 'if(!FileWrite(h,_Symbol,"GLOBAL",0,"OnTimer",ArraySize(g_mcsTimerUs)')
    text = change(text, 'MCSCapture(-1,synthetic,"SYNTH_ALTERNATING");',
        'MCSCapture(_Symbol,"SELFTEST",-1,synthetic,"SYNTH_ALTERNATING",0,0);')
    text = change(text, 'MCSCapture(-2,synthetic,"SYNTH_ZERO_EQUITY");',
        'MCSCapture(_Symbol,"SELFTEST",-2,synthetic,"SYNTH_ZERO_EQUITY",0,0);')
    text = change(text, 'if(!FileWrite(h,"cycle","mode","samples"',
        'if(!FileWrite(h,"symbol","kind","cycle","mode","samples"')
    text = change(text, 'if(!FileWrite(h,s.cycle,mode,s.count',
        'if(!FileWrite(h,s.symbol,s.kind,s.cycle,mode,s.count')
    text = change(text, 'Print(StringFormat("TESTER_MC_SCHEDULER %s',
        'g_mcsMismatches=mismatches;g_mcsComparisons=comparisons;\n Print(StringFormat("TESTER_MC_SCHEDULER %s')
    return text


def build(output, mode=0):
    if mode not in (0, 2):
        raise ValueError('multi-symbol validation supports only modes 0 and 2')
    if hashlib.sha256((SOURCE / STATE).read_bytes()).hexdigest() != SOURCE_STATE_SHA256:
        raise ValueError('source state hash changed; review MC linkage before building')
    output = Path(output).resolve()
    if output == SOURCE.resolve() or SOURCE.resolve() in output.parents or output.exists():
        raise ValueError('Output must be new and outside product src')
    with tempfile.TemporaryDirectory() as td:
        staged = Path(td) / 'base'
        validation_build(staged, mode, qualified=True)
        files = {p.name: p.read_bytes() for p in staged.iterdir()}
    scheduler = qualify_scheduler(files['TesterMCSchedulerDiag.mqh'].decode())
    files['TesterMCSchedulerDiag.mqh'] = (scheduler + '\n#include "TesterMCMultiDiag.mqh"\n').encode()
    main = files[MAIN]
    main = replace_once(main, ' int count=ArraySize(g_symbols),visited=0,scanned=0;',
        ' int count=ArraySize(g_symbols),visited=0,scanned=0;\n for(int mcm=0;mcm<count;mcm++) MCMRegisterSymbol(g_symbols[mcm].m_symbol);MCMArm();')
    main = replace_once(main, ' DispatchQueue();ServiceTradeJournals();RenderDashboard();',
        ' bool mcmNatural=false;for(int mcm=0;mcm<count;mcm++) if(g_symbols[mcm].m_mcActive && !g_symbols[mcm].g_historyDirty) mcmNatural=true;\n MCMSetNaturalActive(mcmNatural);MCMService(deadline);\n DispatchQueue();ServiceTradeJournals();RenderDashboard();')
    main = replace_once(main, 'MCSFinish();MCVExport();return 0;',
        'MCSFinish();MCVExport();MCMExport();return 0;')
    files[MAIN] = main
    files['TesterMCMultiDiag.mqh'] = (TOOLS / 'TesterMCMultiDiag.mqh').read_bytes()
    # Retain the original single-symbol duration allowance for each of the four
    # supported diagnostic symbols. Allocate incrementally; preserve overflow
    # as UNKNOWN and leave all non-duration record limits untouched.
    files['TesterMCSchedulerValidation.mqh'] = replace_once(
        files['TesterMCSchedulerValidation.mqh'],
        'const int MCV_DURATION_LIMIT=3000000;',
        'const int MCV_DURATION_LIMIT=12000000;')
    output.mkdir(parents=True)
    for name, data in files.items():
        (output / name).write_bytes(data)
    return output / MAIN


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', type=int, choices=(0, 2), default=0)
    args = parser.parse_args()
    print(build(args.output, args.mode))
