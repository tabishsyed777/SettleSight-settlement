"""SettleSight build: simulate -> train explainable model -> score live book -> liquidity -> collateral -> audit -> dashboard.
Pure Python (no dependencies). All data is SYNTHETIC."""
import random, math, json, datetime, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
random.seed(11)
FEATS = ["cp_fail_rate","illiquidity","ssi_missing","affirm_delay_h","hrs_to_cutoff","size_pressure"]
LABELS = {"cp_fail_rate":"Counterparty fail history","illiquidity":"Security illiquidity","ssi_missing":"SSI missing or mismatched",
          "affirm_delay_h":"Affirmation delay","hrs_to_cutoff":"Time left to cutoff","size_pressure":"Trade size vs daily volume"}
CPS = {f"CP-{c}": r for c, r in zip("ABCDEFGHIJ",[.01,.015,.02,.03,.035,.05,.07,.09,.12,.16])}
SECS = dict([("US912828","UST 10Y"),("AAPL","Apple"),("MSFT","Microsoft"),("JPM","JPMorgan"),("XOM","Exxon"),
        ("TSLA","Tesla"),("BNYM","BNY"),("SMCP1","SmallCap I"),("SMCP2","SmallCap II"),("HYBND","HY Bond ETF")])
ILLIQ = dict(zip(SECS,[.02,.05,.05,.08,.1,.15,.1,.65,.8,.55]))
TRUE_W = [9.0,2.6,2.2,.55,-.45,1.6]; BIAS = -4.6

def make_trade(i, live):
    cp = random.choice(list(CPS)); sec = random.choice(list(SECS))
    h = random.uniform(.7,5.5) if live else random.uniform(.5,8)
    x = [CPS[cp]+random.gauss(0,.005), ILLIQ[sec]+random.gauss(0,.03), 1 if random.random()<.1 else 0,
         max(0,random.gauss(1.6,1.4)), h, min(1.5,max(0,random.lognormvariate(-1.6,.8)))]
    x[0]=max(0,x[0]); x[1]=min(1,max(0,x[1]))
    p = 1/(1+math.exp(-(BIAS+sum(a*v for a,v in zip(TRUE_W,x)))))
    notional = round(random.lognormvariate(15.6,.9),-3)
    return dict(id=f"T{100000+i}",cp=cp,sec=sec,secname=SECS[sec],x=x,notional=notional,failed=random.random()<p)

hist = [make_trade(i,False) for i in range(6000)]
live = [make_trade(10000+i,True) for i in range(140)]

# Standardise + logistic regression (gradient descent). Score = bias + sum of per-feature contributions => fully explainable.
mu = [sum(t["x"][j] for t in hist)/len(hist) for j in range(6)]
sd = [math.sqrt(sum((t["x"][j]-mu[j])**2 for t in hist)/len(hist)) or 1 for j in range(6)]
Z = lambda x:[(x[j]-mu[j])/sd[j] for j in range(6)]
w=[0.0]*6; b=-2.0; Xs=[Z(t["x"]) for t in hist]; ys=[1 if t["failed"] else 0 for t in hist]
for ep in range(300):
    gw=[0.0]*6; gb=0.0
    for xs,y in zip(Xs,ys):
        e=1/(1+math.exp(-(b+sum(a*c for a,c in zip(w,xs)))))-y
        for j in range(6): gw[j]+=e*xs[j]
        gb+=e
    n=len(Xs); w=[a-.8*g/n for a,g in zip(w,gw)]; b-=.8*gb/n
def predict(x):
    z=Z(x); parts=[w[j]*z[j] for j in range(6)]; s=b+sum(parts)
    return 1/(1+math.exp(-s)), parts
hold=[make_trade(50000+i,False) for i in range(2000)]
sc=[(predict(t["x"])[0],t["failed"]) for t in hold]
pos=[s for s,f in sc if f][:400]; neg=[s for s,f in sc if not f][:1200]
auc=sum((a>c)+.5*(a==c) for a in pos for c in neg)/(len(pos)*len(neg))
base=sum(1 for t in hold if t["failed"])/len(hold)

COST_RATE = .0001 + .05/360 + .0001   # penalty + 1 day funding at 5% + ops cost (illustrative)
ACTION = {"cp_fail_rate":"Escalate to counterparty ops desk","illiquidity":"Source borrow or pre-position the security",
          "ssi_missing":"Request corrected SSI from counterparty","affirm_delay_h":"Chase affirmation now",
          "hrs_to_cutoff":"Move to front of repair queue","size_pressure":"Split settlement into partials"}
NOW = datetime.datetime(2026,11,9,13,20); CUT = NOW+datetime.timedelta(hours=3,minutes=40)
rows=[]; audit=[]
for t in live:
    p,parts=predict(t["x"]); cost=t["notional"]*COST_RATE
    order=sorted(range(6),key=lambda j:-parts[j]); top=[j for j in order if parts[j]>0.05][:3] or order[:1]
    drivers=[dict(label=LABELS[FEATS[j]],c=round(parts[j],2),v=round(t["x"][j],3)) for j in top]
    risk="HIGH" if p>=.30 else "MED" if p>=.12 else "LOW"
    rec=ACTION[FEATS[top[0]]]; save=round(p*cost*.7) if risk!="LOW" else 0
    r=dict(id=t["id"],cp=t["cp"],sec=t["secname"],isin=t["sec"],notional=t["notional"],p=round(p,3),risk=risk,
           exp_cost=round(p*cost),save=save,rec=rec,drivers=drivers,hrs=round(t["x"][4],1))
    rows.append(r)
    if risk=="HIGH": audit.append(dict(ts=(NOW-datetime.timedelta(seconds=random.randint(5,900))).isoformat(timespec="seconds"),
        trade=t["id"],model="logreg-v1.3",score=r["p"],action=rec,why=[f'{d["label"]} (+{d["c"]})' for d in drivers],status="OPEN"))
rows.sort(key=lambda r:-r["p"]); audit.sort(key=lambda a:a["ts"],reverse=True)

# Intraday liquidity ($m): hourly flows; stress case removes expected failed receipts after 14:00
bal=2400.0; liq=[]; thr=2000.0
for h in range(8,19):
    i_=random.uniform(150,420)*(1.3 if h in(9,15) else 1); o_=random.uniform(180,470)*(1.6 if h in(11,16) else 1)
    bal+=i_-o_; liq.append(dict(h=h,i=round(i_),o=round(o_),bal=round(bal)))
fail_m=sum(r["notional"]/1e6*r["p"] for r in rows if r["risk"]!="LOW")
for l in liq: l["stress"]=round(l["bal"]-fail_m*(l["h"]-13)*.9) if l["h"]>=14 else l["bal"]
breach=[l["h"] for l in liq if l["stress"]<thr]

# Collateral ($m): assets = (name, available, haircut, funding cost bps, eligible venues). Greedy cheapest-to-deliver vs naive largest-first.
ASSETS=[("UST 2Y",900,.01,12,["TRI","CCP","BIL"]),("UST 10Y",700,.03,14,["TRI","CCP","BIL"]),("Agency MBS",650,.04,28,["TRI","BIL"]),
        ("IG Corp",500,.08,45,["TRI"]),("Equities (S&P)",400,.15,70,["BIL"]),("Cash USD",300,0,5,["TRI","CCP","BIL"])]
REQ=[("CCP margin","CCP",800),("Tri-party repo","TRI",1100),("Bilateral CSA","BIL",500)]
def alloc(key):
    pool={a[0]:a[1] for a in ASSETS}; out=[]; cost=0.0
    for name,venue,need in REQ:
        got=0.0
        for a in sorted([a for a in ASSETS if venue in a[4]],key=key):
            if got>=need-1e-6: break
            take=min(pool[a[0]],(need-got)/(1-a[2])); pool[a[0]]-=take; got+=take*(1-a[2])
            cost+=take*1e6*a[3]/1e4/365
            out.append(dict(req=name,asset=a[0],pledged=round(take),value=round(take*(1-a[2])),bps=a[3]))
    return out,round(cost)
opt,c_opt=alloc(lambda a:a[3]/(1-a[2])); nai,c_nai=alloc(lambda a:-a[1])
coll=dict(opt=opt,naive=nai,naive_cost=c_nai,opt_cost=c_opt,req=[dict(n=n,need=x) for n,v,x in REQ])

kpi=dict(n=len(rows),high=sum(r["risk"]=="HIGH" for r in rows),med=sum(r["risk"]=="MED" for r in rows),
         at_risk=sum(r["notional"] for r in rows if r["risk"]=="HIGH"),exp_cost=sum(r["exp_cost"] for r in rows),
         save=sum(r["save"] for r in rows),auc=round(auc,3),base=round(base,3),breach=breach,
         now=NOW.strftime("%H:%M"),cutoff=CUT.strftime("%H:%M"),mins=int((CUT-NOW).total_seconds()//60))
DATA=dict(kpi=kpi,trades=rows,liq=liq,thr=thr,coll=coll,audit=audit,labels=LABELS,
          model=dict(weights={FEATS[j]:round(w[j],3) for j in range(6)},bias=round(b,3),auc=kpi["auc"]))
(ROOT/"data/synthetic_output.json").write_text(json.dumps(DATA,indent=1))
(ROOT/"data/audit_log.jsonl").write_text("\n".join(json.dumps(a) for a in audit))
tpl=ROOT/"src/template.html"
if tpl.exists(): (ROOT/"dist/index.html").write_text(tpl.read_text().replace("__DATA__",json.dumps(DATA)))
print(f"AUC={auc:.3f} base_fail={base:.3f} high={kpi['high']} med={kpi['med']} exp_cost=${kpi['exp_cost']:,} saveable=${kpi['save']:,} breach_hours={breach}")
print("collateral $/day naive vs optimised:",c_nai,c_opt)
