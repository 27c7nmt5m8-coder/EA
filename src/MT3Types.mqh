#ifndef MT3_TYPES_MQH
#define MT3_TYPES_MQH
enum ENUM_SCAN_MODE {CURRENT_SYMBOL=0,MARKET_WATCH=1,CUSTOM_LIST=2,ALL_TRADABLE_SYMBOLS=3};
struct VirtualLevel {string name;double price;bool support;};
struct VirtualTrend {datetime t1,t2;double p1,p2;};
enum ENUM_RISK_MODE
  {
   RISK_FIXED_ADJUST = 0,   // 固定リスク + 連敗 + スコア
   RISK_MONTE_CARLO  = 1,   // モンテカルロ
   RISK_COMBINED     = 2    // 統合
  };

enum ENUM_ENTRY_DIRECTION
  {
   ENTRY_BOTH = 0,
   ENTRY_BUY  = 1,
   ENTRY_SELL = 2
  };

struct ThemePropertySnapshot
{
 ENUM_CHART_PROPERTY_INTEGER property;
 long before;
 long applied;
};

enum ENUM_EXECUTION_MODE { EXECUTION_AUTO=0, EXECUTION_MANUAL=1, EXECUTION_AI=2, EXECUTION_HYBRID=3 };

enum ENUM_ACCOUNT_MODE { NORMAL=0, FINTOKEI=1 };

enum ENUM_FINTOKEI_PLAN { FINTOKEI_PROTRADER=0, FINTOKEI_STARTTRADER=1,
                         FINTOKEI_SWIFTTRADER=2, FINTOKEI_PROTRADER_SWING=3 };

struct IndicatorSlot { int kind; ENUM_TIMEFRAMES tf; int period; int handle; };

enum ENUM_PATTERN_TYPE
  {
   PATTERN_NONE = 0,
   PATTERN_DOUBLE_BOTTOM,
   PATTERN_DOUBLE_TOP,
   PATTERN_INVERSE_HEAD_SHOULDERS,
   PATTERN_HEAD_SHOULDERS,
   PATTERN_TRIPLE_BOTTOM,
   PATTERN_TRIPLE_TOP,
   PATTERN_BULLISH_123,
   PATTERN_BEARISH_123,
   PATTERN_BULLISH_FAILED_BREAKOUT,
   PATTERN_BEARISH_FAILED_BREAKOUT
  };

struct PatternSignal
  {
   ENUM_PATTERN_TYPE type;
   string patternId,matchedIds;
   datetime triggerTime,breakoutTime,referenceTime;
   double referencePrice;

   bool   valid;

   bool   buySignal;

   bool   sellSignal;

   double firstPoint;

   double secondPoint;

   double headPoint;

   double neckline;

   double entryLevel;

   double patternStrength;

   datetime firstTime;

   datetime secondTime;

   datetime headTime;

   datetime necklineTime;
  };

struct MTFResult
  {
   ENUM_TIMEFRAMES timeframe;
   datetime bar;double atr,close,previousFast,previousMiddle,previousSlow,previousHistogram,slopeATR;
   double orderEvidence,slopeEvidence,diEvidence,priceEvidence,spacingEvidence;

   double emaFast;
   double emaMiddle;
   double emaSlow;

   double adx;
   double plusDI;
   double minusDI;

   double macdMain;
   double macdSignal;
   double macdHistogram;

   double trendScore;
   double macdScore;
   double totalScore;

   int trendDirection;
   int macdDirection;

   bool trendStrong;
  };

struct PendingAIDecision
{
 bool active,hybrid,buy;datetime bar;ulong started;long worker;double token,score,bid,ask;
 string id,registry;PatternSignal pattern;
};
#endif
