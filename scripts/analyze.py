import json, math, datetime, pathlib, time
import yfinance as yf

ROOT=pathlib.Path(__file__).resolve().parents[1]
# 감시 후보군: 전체 시장이 아닌 명시적 30종목
KR={'005930.KS':'삼성전자','000660.KS':'SK하이닉스','402340.KS':'SK스퀘어','005380.KS':'현대차','012330.KS':'현대모비스','028260.KS':'삼성물산','032830.KS':'삼성생명','086790.KS':'하나금융지주','298040.KS':'효성중공업','000270.KS':'기아','035420.KS':'NAVER','035720.KS':'카카오','105560.KS':'KB금융','055550.KS':'신한지주','066570.KS':'LG전자'}
US={'INTU':'Intuit','ADBE':'Adobe','ACN':'Accenture','FIS':'Fidelity National Information Services','AVGO':'Broadcom','MSFT':'Microsoft','AAPL':'Apple','NVDA':'NVIDIA','GOOGL':'Alphabet','AMZN':'Amazon','META':'Meta','CRM':'Salesforce','PYPL':'PayPal','AMD':'AMD','QCOM':'Qualcomm'}

def valid(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None

def inspect(ticker,name,market):
    obj=yf.Ticker(ticker)
    hist=obj.history(period='1y',auto_adjust=False)
    if len(hist)<65:return None
    close=hist['Close'].dropna();vol=hist['Volume'].dropna()
    if len(close)<65:return None
    price=valid(close.iloc[-1]);high=valid(hist['High'].max());drop=(price/high-1)*100 if price and high else None
    delta=close.diff();gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    l=valid(loss.iloc[-1]);g=valid(gain.iloc[-1]);rsi=100 if l==0 and g and g>0 else (100-100/(1+g/l) if l and g is not None else None)
    v20=valid(vol.tail(20).mean());vprev=valid(vol.iloc[-40:-20].mean());voldecline=bool(v20<vprev) if v20 is not None and vprev is not None else None
    trend=bool(price<valid(close.tail(60).mean())) if price else None
    info={}
    try:info=obj.info or {}
    except Exception:pass
    pe=valid(info.get('trailingPE'));pb=valid(info.get('priceToBook'))
    op=valid(info.get('operatingIncome'));de=valid(info.get('debtToEquity'))
    # Yahoo debtToEquity is percentage (e.g. 50 means 50%) and may be missing.
    passed=bool(drop is not None and drop<=-20 and voldecline and trend and op is not None and op>0 and de is not None and de<=150 and pe is not None and pe>0 and pb is not None and pb>0)
    return {'ticker':ticker,'name':name,'market':market,'price':price,'currency':'KRW' if market=='KR' else 'USD','drop_from_52w_pct':round(drop,1) if drop is not None else None,'rsi14':round(rsi,1) if rsi is not None else None,'volume_declining':voldecline,'below_ma60':trend,'per':round(pe,2) if pe is not None else None,'pbr':round(pb,2) if pb is not None else None,'operating_income':op,'debt_to_equity_pct':round(de,1) if de is not None else None,'passed':passed,'source':'Yahoo Finance (yfinance)','price_date':str(close.index[-1].date())}

def main():
    results=[];fail=[]
    for market,universe in [('KR',KR),('US',US)]:
        for ticker,name in universe.items():
            try:
                row=inspect(ticker,name,market)
                if row:results.append(row)
                else:fail.append(ticker+': 데이터 부족')
            except Exception as e:fail.append(ticker+': '+str(e)[:100])
            time.sleep(.2)
    passed=[r for r in results if r['passed']]
    passed.sort(key=lambda r:(r['market'],r['drop_from_52w_pct']))
    picks={m:[r for r in passed if r['market']==m][:5] for m in ('KR','US')}
    payload={'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'지정된 30종목 중 52주 고점 -20% 이하, 20일 평균 거래량 감소, 60일 이평 아래, 영업이익 양수, PER/PBR 양수, 부채/자기자본 150% 이하','universe_count':len(KR)+len(US),'checked_count':len(results),'failed_count':len(fail),'failures':fail,'recommendations':picks,'note':'자동 정량 필터 결과이며 매수 추천이 아닙니다. 데이터 제공처의 결측·지연·정의 차이가 있을 수 있습니다. RSI는 참고지표이며 필터 필수조건은 아닙니다.'}
    (ROOT/'recommendations.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print('checked',len(results),'picks',sum(map(len,picks.values())),'failures',len(fail))
if __name__=='__main__':main()
