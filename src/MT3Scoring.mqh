#ifndef MT3_SCORING_MQH
#define MT3_SCORING_MQH
// Pure, closed-bar, ATR-normalized scoring. Signed evidence is in [-100,100].
double Clip(double x) {return MathMax(-1.0,MathMin(1.0,x));}
int Sign(double x) {return x>0?1:(x<0?-1:0);}
double DirectionalScore(double evidence,bool buy)
{return MathMax(0.0,MathMin(100.0,50.0+(buy?evidence:-evidence)*0.5));}
ENUM_TIMEFRAMES MT3Timeframe(int i)
{
 switch(i) {case 0:return PERIOD_M1;case 1:return PERIOD_M5;case 2:return PERIOD_M15;
 case 3:return PERIOD_M30;case 4:return PERIOD_H1;case 5:return PERIOD_H4;case 6:return PERIOD_D1;}
 return PERIOD_M1;
}
double MT3Weight(ENUM_TIMEFRAMES tf)
{
 switch(tf) {case PERIOD_M1:return 20;case PERIOD_M5:return 25;case PERIOD_M15:return 22;
 case PERIOD_M30:return 15;case PERIOD_H1:return 10;case PERIOD_H4:return 5;case PERIOD_D1:return 3;}
 return 0;
}
void MACDParameters(ENUM_TIMEFRAMES tf,int &fast,int &slow,int &signal)
{
 fast=12;slow=26;signal=9;
 switch(tf)
 {
 case PERIOD_M1:fast=MACDM1Fast;slow=MACDM1Slow;signal=MACDM1Signal;break;
 case PERIOD_M5:fast=MACDM5Fast;slow=MACDM5Slow;signal=MACDM5Signal;break;
 case PERIOD_M15:fast=MACDM15Fast;slow=MACDM15Slow;signal=MACDM15Signal;break;
 case PERIOD_M30:fast=MACDM30Fast;slow=MACDM30Slow;signal=MACDM30Signal;break;
 case PERIOD_H1:fast=MACDH1Fast;slow=MACDH1Slow;signal=MACDH1Signal;break;
 case PERIOD_H4:fast=MACDH4Fast;slow=MACDH4Slow;signal=MACDH4Signal;break;
 case PERIOD_D1:fast=MACDD1Fast;slow=MACDD1Slow;signal=MACDD1Signal;break;
 }
}
double ADXStrength(double adx)
{
 if(adx<15) return MathMax(0.0,adx/15.0*0.25);
 if(adx<20) return 0.25+(adx-15)*0.04;
 if(adx<25) return 0.45+(adx-20)*0.04;
 if(adx<35) return 0.65+(adx-25)*0.035;
 return 1.0;
}
void ScoreEvidence(MTFResult &r)
{
 r.orderEvidence=15*Sign(r.emaFast-r.emaMiddle)+15*Sign(r.emaMiddle-r.emaSlow);
 r.slopeATR=(0.6*(r.emaFast-r.previousFast)+0.3*(r.emaMiddle-r.previousMiddle)+
             0.1*(r.emaSlow-r.previousSlow))/(r.atr*EMASlopeBars);
 r.slopeEvidence=20*Clip(r.slopeATR/0.10);
 double diTotal=r.plusDI+r.minusDI;
 r.diEvidence=diTotal>0?25*ADXStrength(r.adx)*Clip((r.plusDI-r.minusDI)/diTotal/0.35):0;
 r.priceEvidence=15*(0.5*Clip((r.close-r.emaFast)/(r.atr*0.10))+
                         0.3*Clip((r.close-r.emaMiddle)/(r.atr*0.10))+
                         0.2*Clip((r.close-r.emaSlow)/(r.atr*0.10)));
 r.spacingEvidence=10*Clip((r.emaFast-r.emaSlow)/(r.atr*1.5));
 r.trendScore=r.orderEvidence+r.slopeEvidence+r.diEvidence+r.priceEvidence+r.spacingEvidence;
 r.macdScore=45*Clip(r.macdHistogram/(r.atr*0.05))+25*Clip(r.macdMain/(r.atr*0.20))+
             30*Clip((r.macdHistogram-r.previousHistogram)/(r.atr*0.025));
 r.totalScore=r.trendScore*0.70+r.macdScore*0.30;
 r.trendDirection=MathAbs(r.trendScore)>=10?Sign(r.trendScore):0;
 r.macdDirection=MathAbs(r.macdScore)>=10?Sign(r.macdScore):0;
 r.trendStrong=MathAbs(r.trendScore)>=50 && r.adx>=25;
}
bool CompleteMTF(MTFResult &r[])
{
 if(ArraySize(r)!=7) return false;
 for(int i=0;i<7;i++) if(r[i].timeframe!=MT3Timeframe(i) || r[i].atr<=0) return false;
 return true;
}
double WeightedAgreement(MTFResult &r[],bool buy)
{
 if(!CompleteMTF(r)) return 0;
 double total=0;int side=buy?1:-1;
 for(int i=0;i<7;i++) if(r[i].trendDirection==side) total+=MT3Weight(r[i].timeframe);
 return total;
}
double WeightedMTFScore(MTFResult &r[],bool buy)
{
 if(!CompleteMTF(r)) return 0;
 double total=0;for(int i=0;i<7;i++) total+=MT3Weight(r[i].timeframe)*r[i].totalScore/100.0;
 return DirectionalScore(total,buy);
}
bool StrongHigherOpposition(MTFResult &r[],bool buy)
{
 if(!CompleteMTF(r)) return true;
 int side=buy?1:-1;
 for(int i=4;i<=5;i++)
  if(side*r[i].trendScore>-50 || r[i].adx<25 || side*(r[i].plusDI-r[i].minusDI)>=0) return false;
 return true;
}
bool StrongFastMACDOpposition(MTFResult &r[],bool buy)
{
 if(!CompleteMTF(r)) return true;
 int side=buy?1:-1;
 for(int i=0;i<2;i++)
  if(side*r[i].macdScore>-50 || side*r[i].macdHistogram/r[i].atr>-0.03) return false;
 return true;
}
bool WeightedSignalOK(MTFResult &r[],bool buy)
{return CompleteMTF(r) && WeightedAgreement(r,buy)>=MinimumWeightedAgreement &&
        !StrongHigherOpposition(r,buy) && !StrongFastMACDOpposition(r,buy);}

double Score100(double value)
{return MathIsValidNumber(value)?MathMax(0.0,MathMin(100.0,value)):0.0;}
bool ValidateFinalWeights()
{
 if(!MathIsValidNumber(FinalMTFWeight) || !MathIsValidNumber(FinalPatternWeight) || !MathIsValidNumber(FinalLineWeight) ||
    FinalMTFWeight<0 || FinalMTFWeight>100 || FinalPatternWeight<0 || FinalPatternWeight>100 || FinalLineWeight<0 || FinalLineWeight>100)
 {Print("Final score weights must each be finite and between 0 and 100.");return false;}
 double sum=FinalMTFWeight+FinalPatternWeight+FinalLineWeight;
 if(MathAbs(sum-100.0)>0.001)
 {PrintFormat("Final score weights sum to %.8f; required 100 (tolerance 0.001). No automatic normalization.",sum);return false;}
 return true;
}
double FinalSignalScore(double mtf,double pattern,double line)
{
 double normalizedLine=Score100(line*5.0); // Legacy LineScore range is 0..20.
 return Score100(Score100(mtf)*FinalMTFWeight/100.0+Score100(pattern)*FinalPatternWeight/100.0+
                 normalizedLine*FinalLineWeight/100.0);
}
#endif
