"""Record computed parity, synthetic plane behaviour and runtime versions."""
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import scipy
import matplotlib
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT))
from tapp.lab_geometry import geometry_layer_cost

rows=[]
for angle in (5,12,22,30):
    z=np.indices((11,11))[0]*.5*np.tan(np.deg2rad(angle))
    slope,cost=geometry_layer_cost(z,.5)
    rows.append(dict(physical_plane_deg=angle,geometry_angle_deg=float(np.arctan(slope[5,5])*57.3),ros_cost=int(cost[5,5])))
planes=pd.DataFrame(rows)
planes.to_csv(OUT/'plane_audit.csv',index=False)
parity=pd.read_csv(OUT.parent/'parity.csv')
assert parity.matched.all()
data=pd.read_csv(OUT.parent/'runs.csv')
assert len(data)==768 and data.success.all()
assert not any('energy' in c.lower() for c in data.columns)
env=dict(python=sys.version,executable=sys.executable,prefix=sys.prefix,base_prefix=sys.base_prefix,
         venv=sys.prefix!=sys.base_prefix,system_site_packages=True,numpy=np.__version__,scipy=scipy.__version__,
         pandas=pd.__version__,matplotlib=matplotlib.__version__)
(OUT/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
log=planes.to_string(index=False)+'\n\n'+json.dumps(dict(
    scenarios=len(data)//4,runs=len(data),parity_fields=len(parity),all_matched=bool(parity.matched.all()),
    maximum_absolute_difference=float(parity.absolute_difference.max()),
    failed_runs=int((~data.success).sum())),indent=2)+'\n'
(OUT/'diagnostics_log.txt').write_text(log)
print(log,end='')
