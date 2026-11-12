import math
# numbers printed by diag_g9b.py for KWS fused stage, tile n=8, co=64 (512 outputs), nvm scale 1.0
px=512
Cu,Tu=1.9739e-08*px,2.6514e-06*px                 # unchunked: energy J, active time s
Cs,Ts=5.7257e-08*px,6.2162e-06*px                 # chunk16, z1+ps1 (4 chunks)
Cp,Tp=4.7878e-08*px,5.3250e-06*px                 # chunk16, ps1 only
def seg(c,t,lam):
    x=lam*t
    return c*math.expm1(x)/x if x>0 else c          # restart-until-success, recovery ignored (favours neither)
def E_unchunked(lam): return seg(Cu,Tu,lam)
def E_saved(C,T,lam,k=4): return k*seg(C/k,T/k,lam)
print('tile: unchunked %.2f uJ %.2f ms ; z1ps1 %.2f uJ %.2f ms ; ps1 %.2f uJ'%(Cu*1e6,Tu*1e3,Cs*1e6,Ts*1e3,Cp*1e6))
print('write overhead of z1ps1 vs unchunked: +%.0f%%'%(100*(Cs/Cu-1)))
for lam in (2,16,100,300,500,1000,2000,5000):
    print('lam %5d Hz  P(outage in tile)=%.3f  E_unchunked=%.2f uJ  E_z1ps1=%.2f uJ  E_ps1=%.2f uJ'%(lam,1-math.exp(-lam*Tu),E_unchunked(lam)*1e6,E_saved(Cs,Ts,lam)*1e6,E_saved(Cp,Tp,lam)*1e6))
lo,hi=1.,1e5
for _ in range(80):
    mid=math.sqrt(lo*hi)
    if E_saved(Cp,Tp,mid)<E_unchunked(mid): hi=mid
    else: lo=mid
print('break-even hazard (ps1 vs unchunked), full-exposure model: ~%.0f Hz'%hi)
