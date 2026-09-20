#ifndef MT3_CONFIG_MQH
#define MT3_CONFIG_MQH
input group "=== TradingView Style ==="
input bool EnableTradingViewTheme=true;
input bool ThemeShowGrid=false;
input int ThemeChartScale=3;             // MT5 scale 0..5
input double ThemeRightMarginPercent=15; // Chart shift 10..50 percent
input group "=== Auto / Discretionary / AI Entry ==="
input ENUM_EXECUTION_MODE ExecutionMode=EXECUTION_AUTO;
input bool EnableManualTrading=true;
input double ManualInitialSL=0.0; // 0 = remembered line or initial preview placement
input group "=== OpenAI AI Filter ==="
input bool EnableOpenAI=false;
input string OpenAIModel="gpt-5.6-luna";
input string OpenAIReasoningEffort="low"; // Empty string omits reasoning for models without this option.
input int OpenAIMaxDecisionAgeMs=10000;
input int OpenAIMaxQuoteAgeMs=3000;
input double OpenAIMaxPriceDriftPoints=0;
input double OpenAIMinConfidence=0.70;
input int OpenAIM1Bars=24;
input bool OpenAIFailOpen=false; // HYBRID only: allow local strategy on transport errors; invalid/refused/incomplete responses always block.
input group "=== Order Reconciliation ==="
input string ReconciledOrderToken=""; // One-use token, ONLY after confirming the unresolved order outcome with the broker.
input group "=== General ==="
input ulong MagicNumber = 26090201;
input ENUM_ENTRY_DIRECTION EntryDirection = ENTRY_BOTH;
input bool EnableAutoTrading = true;
input bool OnePositionPerSymbol = true;
input bool OneEntryPerBar = true;
input int MaxSpreadPoints =0;
input group "=== Multi Timeframe ==="
input group "=== EMA ==="
input int EMAFastPeriod   = 20;
input int EMAMiddlePeriod = 50;
input int EMASlowPeriod   = 200;
input group "=== ADX ==="
input int ADXPeriod = 14;
input group "=== MACD ==="
input group "=== Swing / Pattern ==="
input int SwingDepth = 5;
input int PatternLookbackBars = 150;
input double PatternToleranceATR = 0.30;
input bool EnableTripleBottom = true;
input bool EnableTripleTop = true;
input double TripleMinimumReboundATR = 0.20; // Each of the two intervening rebounds
input double NecklineToleranceATR = 0.10;
input group "=== Signal Score ==="
input double MinimumSignalScore = 70.0;
input group "=== Risk Management ==="
input ENUM_RISK_MODE RiskMode = RISK_COMBINED;
input double BaseRiskPercent = 0.50;
input double MinimumRiskPercent = 0.10;
input double MaximumRiskPercent = 1.00;
input group "=== Consecutive Loss Adjustment ==="
input double RiskAfter2Loss = 0.40;
input double RiskAfter3Loss = 0.30;
input double RiskAfter4Loss = 0.20;
input double RiskAfter5Loss = 0.10;
input int StopAfterConsecutiveLosses = 6;
input group "=== Score Risk Adjustment ==="
input double RiskScore90 = 0.50;
input double RiskScore80 = 0.40;
input double RiskScore70 = 0.30;
input group "=== Monte Carlo ==="
input bool EnableMonteCarlo = true;
input int MonteCarloRuns = 10000;
input int MonteCarloTrades = 200;
input double MonteCarloMaxDrawdownPercent = 20.0;
input double MonteCarloSafetyFactor = 0.80;
input double MonteCarloMinimumWinRate = 0.40;
input group "=== SL / TP ==="
input bool UseSwingStopLoss = true;
input int StopSwingLookback = 20;
input double SLBufferPoints =0;
input double RiskRewardRatio = 1.0;
input group "=== Auto Horizontal Lines ==="
input bool EnableAutoHorizontalLines = true;
input ENUM_TIMEFRAMES LineTimeframe = PERIOD_M15;
input int MaxHorizontalLines = 10;
input double HorizontalLineToleranceATR = 0.25;
input group "=== Auto Trend Lines ==="
input bool EnableAutoTrendLines = true;
input bool ShowAutoTrendLines = false; // Drawing only; virtual trends and LineScore are unchanged.
input int TrendLineSwingDepth = 5;
input group "=== Execution / History ==="
input ENUM_ACCOUNT_MODE AccountMode=NORMAL;
input int SlippagePoints=0;
input double RoundTurnCommissionPerLot=0.0; // Account currency, estimated total commission
input int StopSlippageBufferPoints=0;     // Extra sizing reserve; not a fill guarantee
input int HistoryTradeLimit=200;
input int MonteCarloMinimumSamples=30;
input int MonteCarloRecalculateMinutes=30;
input double MonteCarloRiskStep=0.05;
input int MonteCarloSeed=260906;
input double BreakEvenMoneyTolerance=0.01; // Account currency
input datetime LossStreakResetTime=0;       // Explicit manual reset cutoff (server time)
input bool RunSelfTestsOnInit=false;
input group "=== Smart BE / Trailing ==="
input bool EnableSmartBreakEven=true;
input double BreakEvenTriggerR=0.60;
input double BreakEvenLockR=0.05;
input double ProfitLockTriggerR=0.80;
input double ProfitLockR=0.20;
input double ProfitLock2TriggerR=0.90;
input double ProfitLock2R=0.40;
input bool EnableATRTrailing=true;
input double ATRTrailingMultiplier=0.80;
input bool EnableStructureTrailing=true;
input int StructureTrailingLookback=20;
input int MinimumSLImprovementPoints=0;
input group "=== Fintokei DD Protection ==="
input ENUM_FINTOKEI_PLAN FintokeiPlan=FINTOKEI_PROTRADER;
input double FintokeiInitialBalance=0;       // REQUIRED: original account starting capital
input double FintokeiDailyReference=0;       // REQUIRED initially: official UTC daily equity/balance
input datetime FintokeiReferenceDateUTC=0;   // UTC date to which the above reference belongs
input double FintokeiSafetyMargin=0.80;
input double FintokeiMaxRiskPerTrade=0.50;
input int FintokeiMaxConsecutiveLosses=5;
input double FintokeiExtraReservePercent=0.10; // Original capital reserve
input int TesterServerUTCOffsetHours=0;     // Set to historical server offset for testing
input group "=== v2.42 Multi Symbol ==="
input ENUM_SCAN_MODE ScanMode=MARKET_WATCH;
input string CustomSymbols="";
input int ScanTimerMilliseconds=1000;
input int SymbolsPerTimer=20;
input int ScanBudgetMilliseconds=150;
input int UniverseRefreshSeconds=60;
input int MaxEntriesPerTimer=2;
input int DashboardRows=8;
input int MaxQuoteAgeMs=3000;
input int MonteCarloTimerBudgetMs=20;
input group "=== v2.42 Weighted MTF ==="
input double MinimumWeightedAgreement=55.0;
input int EMASlopeBars=3;
input group "=== v2.42 Relative Costs ==="
input double MaxSpreadATR=0.10;
input double MaxSpreadSL=0.15;
input double SLBufferATR=0.05;
input double SlippageATR=0.02;
input double StopSlippageATR=0.02;
input double MinimumSLImprovementATR=0.01;
input double OpenAIMaxPriceDriftATR=0.10;
input group "=== v2.42 MACD by Timeframe ==="
input int MACDM1Fast=8;
input int MACDM1Slow=21;
input int MACDM1Signal=5;
input int MACDM5Fast=8;
input int MACDM5Slow=21;
input int MACDM5Signal=5;
input int MACDM15Fast=12;
input int MACDM15Slow=26;
input int MACDM15Signal=9;
input int MACDM30Fast=12;
input int MACDM30Slow=26;
input int MACDM30Signal=9;
input int MACDH1Fast=12;
input int MACDH1Slow=26;
input int MACDH1Signal=9;
input int MACDH4Fast=12;
input int MACDH4Slow=26;
input int MACDH4Signal=9;
input int MACDD1Fast=12;
input int MACDD1Slow=26;
input int MACDD1Signal=9;
input group "=== v2.43 Final Score Weights (sum = 100) ==="
input double FinalMTFWeight = 80.0;
input double FinalPatternWeight = 15.0;
input double FinalLineWeight = 5.0;
input group "=== v2.44 Portfolio Risk / Analytics ==="
input bool EnablePortfolioRiskLimit = true;
input double MaxPortfolioRiskPercent = 3.0;
input bool EnableTradeLog = true;
#endif
