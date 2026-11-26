import numpy as np, sys
from experiments import false_steep_inspect as F
from results.false_steep_causes import replay as A
from tapp.traversability import slope_deg
root=A.ROOT; tr=A.committed_inputs(root)
tot=dict(n=0,hi_obs=0,hi_w02=0,hi_w05=0,lo_w02=0,cen_w02=0, hi_err_obs=[], hi_err_far=[])
for raw,meta,_ in A.discover(root,tr):
    if not meta: continue
    _,_,_,_,truth,water,nodata,mapper,_,terrain=A.read_record(root,tr,raw,meta)
    fm=F.read_final(root/raw/'pointcloud_map.npz',truth.elev.shape)
    land=~(water|nodata); e=fm['elev']; seen=fm['seen']
    sel=seen&land&(slope_deg(truth.elev)<=25)&(slope_deg(e)>25)
    cells=np.argwhere(sel); p=F.stencil(e,truth.elev,seen,land,cells)
    sx=np.abs(p['x']['gradient'])>=np.abs(p['y']['gradient'])
    hi=tuple(np.where(sx,p['x']['high'][k],p['y']['high'][k]) for k in (0,1))
    lo=tuple(np.where(sx,p['x']['low'][k],p['y']['low'][k]) for k in (0,1))
    d=A.fine_distance(fm['fine_obstacle'])
    fo=fm['fine_obstacle']; R=F.RATIO
    obs_coarse=fo.reshape(fo.shape[0]//R,R,fo.shape[1]//R,R).any(axis=(1,3))
    err=e[hi]-truth.elev[hi]
    tot['n']+=len(cells); tot['hi_obs']+=int(obs_coarse[hi].sum())
    tot['hi_w02']+=int((d[hi]<=.2+1e-12).sum()); tot['hi_w05']+=int((d[hi]<=.5+1e-12).sum())
    tot['lo_w02']+=int((d[lo]<=.2+1e-12).sum()); tot['cen_w02']+=int((d[tuple(cells.T)]<=.2+1e-12).sum())
    tot['hi_err_obs']+=list(err[obs_coarse[hi]]); tot['hi_err_far']+=list(err[~obs_coarse[hi]])
for k in ('n','hi_obs','hi_w02','hi_w05','lo_w02','cen_w02'): print(k,tot[k])
print('hi err median: endpoint has fine obstacle',np.median(tot['hi_err_obs']),len(tot['hi_err_obs']),' / none',np.median(tot['hi_err_far']),len(tot['hi_err_far']))
