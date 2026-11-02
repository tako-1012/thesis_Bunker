"""GRS80 Gauss-Krueger conversion, Japan Plane Rectangular CS VIII (numpy only).

Source: Geospatial Information Authority of Japan, survey calculation formulae:
https://vldb.gsi.go.jp/sokuchi/surveycalc/surveycalc/algorithm/bl2xy/bl2xy.htm
https://vldb.gsi.go.jp/sokuchi/surveycalc/surveycalc/algorithm/xy2bl/xy2bl.htm
The fifth-order third-flattening series is Kawase's formulation. X is northing,
Y easting. This projects coordinates; it does not transform epochs or datums.
JGD2011/JGD2024 use the same GRS80 ellipsoid/projection constants here.
"""

import numpy as np

A=6378137.0
F=298.257222101
M0=.9999
N=1/(2*F-1)
PHI0=np.radians(36.)
LAMBDA0=np.radians(138.5)


def _series():
    n=N
    meridian=np.array([1+n**2/4+n**4/64,
        -3/2*(n-n**3/8-n**5/64),15/16*(n**2-n**4/4),
        -35/48*(n**3-5*n**5/16),315/512*n**4,-693/1280*n**5])
    alpha=np.array([n/2-2*n**2/3+5*n**3/16+41*n**4/180-127*n**5/288,
        13*n**2/48-3*n**3/5+557*n**4/1440+281*n**5/630,
        61*n**3/240-103*n**4/140+15061*n**5/26880,
        49561*n**4/161280-179*n**5/168,34729*n**5/80640])
    beta=np.array([n/2-2*n**2/3+37*n**3/96-n**4/360-81*n**5/512,
        n**2/48+n**3/15-437*n**4/1440+46*n**5/105,
        17*n**3/480-37*n**4/840-209*n**5/4480,
        4397*n**4/161280-11*n**5/504,4583*n**5/161280])
    delta=np.array([2*n-2*n**2/3-2*n**3+116*n**4/45+26*n**5/45,
        7*n**2/3-8*n**3/5-227*n**4/45+2704*n**5/315,
        56*n**3/15-136*n**4/35-1262*n**5/105,
        4279*n**4/630-332*n**5/35,4174*n**5/315])
    scale=M0*A/(1+n)
    origin=scale*(meridian[0]*PHI0+sum(meridian[j]*np.sin(2*j*PHI0) for j in range(1,6)))
    return scale*meridian[0],origin,alpha,beta,delta


BAR_A,S0,ALPHA,BETA,DELTA=_series()


def _inputs(a,b,zone):
    if zone != 8:
        raise ValueError("only Japanese zone 8 is supported")
    a,b=np.broadcast_arrays(np.asarray(a,float),np.asarray(b,float))
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("coordinates must be finite")
    return a,b


def plane_to_latlon(X,Y,zone=8):
    """North/east metres to latitude/longitude degrees, GRS80 zone VIII."""
    X,Y=_inputs(X,Y,zone)
    xi,eta=(X+S0)/BAR_A,Y/BAR_A
    xp=xi.copy();ep=eta.copy()
    for j,b in enumerate(BETA,1):
        xp=xp-b*np.sin(2*j*xi)*np.cosh(2*j*eta)
        ep=ep-b*np.cos(2*j*xi)*np.sinh(2*j*eta)
    chi=np.arcsin(np.sin(xp)/np.cosh(ep))
    phi=chi.copy()
    for j,d in enumerate(DELTA,1):
        phi=phi+d*np.sin(2*j*chi)
    lon=LAMBDA0+np.arctan2(np.sinh(ep),np.cos(xp))
    return np.degrees(phi),np.degrees(lon)


def latlon_to_plane(lat,lon,zone=8):
    """Latitude/longitude degrees to north/east metres, GRS80 zone VIII."""
    lat,lon=_inputs(lat,lon,zone)
    if (np.abs(lat)>=90).any() or (np.abs(lon-138.5)>=90).any():
        raise ValueError("coordinates outside the zone-VIII projection domain")
    phi=np.radians(lat);dl=np.radians(lon)-LAMBDA0
    e=2*np.sqrt(N)/(1+N)
    t=np.sinh(np.arctanh(np.sin(phi))-e*np.arctanh(e*np.sin(phi)))
    xi=np.arctan2(t,np.cos(dl))
    eta=np.arctanh(np.sin(dl)/np.sqrt(1+t*t))
    x=xi.copy();y=eta.copy()
    for j,a in enumerate(ALPHA,1):
        x=x+a*np.sin(2*j*xi)*np.cosh(2*j*eta)
        y=y+a*np.cos(2*j*xi)*np.sinh(2*j*eta)
    return BAR_A*x-S0,BAR_A*y


def _geometry(meta):
    origin=np.asarray(meta["origin_xy"],float)
    tangent=np.asarray(meta["tangent"],float)
    normal=np.asarray(meta["normal"],float)
    offset=np.asarray(meta["offset_uv_m"],float)
    if any(x.shape!=(2,) or not np.isfinite(x).all() for x in (origin,tangent,normal,offset)):
        raise ValueError("invalid map geographic geometry")
    axes=np.array([tangent,normal])
    if not np.allclose(axes@axes.T,np.eye(2),atol=1e-10,rtol=0):
        raise ValueError("map axes must be orthonormal")
    return origin,tangent,normal,offset


def map_xy_to_latlon(meta,x,y):
    """Map metres (first cell centre = 0,0) to latitude/longitude degrees."""
    x,y=_inputs(x,y,meta["zone"])
    origin,t,n,offset=_geometry(meta)
    u,v=x+offset[0],y+offset[1]
    X=origin[0]-(u*t[0]+v*n[0])
    Y=origin[1]+u*t[1]+v*n[1]
    return plane_to_latlon(X,Y,zone=meta["zone"])


def latlon_to_map_xy(meta,lat,lon):
    """Latitude/longitude to map metres, inverse of patch_to_plane geometry."""
    origin,t,n,offset=_geometry(meta)
    X,Y=latlon_to_plane(lat,lon,zone=meta["zone"])
    di,dj=origin[0]-X,Y-origin[1]
    return di*t[0]+dj*t[1]-offset[0],di*n[0]+dj*n[1]-offset[1]
