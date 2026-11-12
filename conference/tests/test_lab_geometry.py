"""Task031 independent neighbour oracle, NavFn source constants and 013 parity."""
import heapq
import math
from pathlib import Path
import numpy as np
from tapp.lab_geometry import geometry_layer_cost, navfn_cell_cost, plan_lab, obstacle_mask
from tapp.collision import path_lethal_cells

ROOT = Path(__file__).resolve().parents[1]

def test_geometry():
    z = np.zeros((11, 11)); slope, cost = geometry_layer_cost(z, .5)
    assert np.all(slope[1:-1, 1:-1] == 0) and np.all(cost[1:-1, 1:-1] == 0)
    assert np.isnan(slope[0, 0]) and cost[0, 0] == 255
    for degrees in (5, 12, 22, 30):
        z = np.indices((11, 11))[0]*.5*math.tan(math.radians(degrees))
        actual, costs = geometry_layer_cost(z, .5)
        values = [abs(z[5+dx, 5+dy]-z[5, 5])/(.5*(1.41 if dx and dy else 1))
                  for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
        expected = sum(values)/8
        angle = math.atan(expected)*57.3
        coeff = next((v for t,v in ((5,0),(10,.1),(15,.2),(20,.5),(25,.8)) if angle <= t),1)
        assert np.isclose(actual[5,5], expected) and costs[5,5] == int(coeff*254)
    # Planes with prescribed GeometryLayer angles (not physical plane angles).
    scale = (2+4/1.41)/8
    for angle, expected in ((4,0),(7,25),(12,50),(17,127),(22,203),(30,254)):
        z = np.indices((11, 11))[0]*.5*math.tan(angle/57.3)/scale
        _, c = geometry_layer_cost(z, .5)
        assert c[5,5] == expected, (angle,c[5,5])
    print('1 PASS: flat terrain and physical 5/12/22/30deg planes match independent eight-neighbour formula; all six cost stages and uint8 truncation')

def test_unknown():
    z = np.full((5,5), np.nan); z[2,2] = 0
    for p in ((1,2),(2,1),(2,3)): z[p] = 0
    assert geometry_layer_cost(z,.5)[1][2,2] == 255
    z[3,2] = 0
    assert geometry_layer_cost(z,.5)[1][2,2] == 0
    assert geometry_layer_cost(z,.5)[1][0,0] == 255
    print('2 PASS: <=3 valid neighbours and absent centres stay unknown; fourth valid neighbour enables cost')

def test_navfn():
    values = np.array([0,25,50,127,203,252,253,254,255],np.uint8)
    assert navfn_cell_cost(values).tolist() == [50,70,90,151,212,251,254,254,253]
    cpp = (ROOT/'results/lab_baseline/sources/navfn.cpp').read_text()
    hpp = (ROOT/'results/lab_baseline/sources/navfn.hpp').read_text()
    for text in ('v = COST_NEUTRAL + COST_FACTOR * v;', 'v = COST_OBS - 1;', 'allow_unknown'):
        assert text in cpp
    for text in ('#define COST_NEUTRAL 50','#define COST_FACTOR 0.8','#define COST_OBS_ROS 253','#define COST_UNKNOWN_ROS 255'):
        assert text in hpp
    print('3 PASS: pinned Jazzy setCostmap integer conversion, 253/254 blockage and allowed unknown=253')

def test_paths():
    n=11; z=np.zeros((n,n)); raw=np.zeros((n,n),bool);raw[5,:8]=True
    result=plan_lab(z,raw,(2,2),(8,2))
    assert result['success'] and len(path_lethal_cells(result['path'],raw)) == 0
    # Independent Dijkstra checks the specified symmetric eight-neighbour graph.
    c=navfn_cell_cost(geometry_layer_cost(z,.5)[1]).astype(float)
    raw[[0,-1],:]=True; raw[:,[0,-1]]=True
    dist={(2,2):0.}; heap=[(0.,(2,2))]
    while heap:
        d,u=heapq.heappop(heap)
        if d != dist[u]: continue
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                v=(u[0]+dx,u[1]+dy)
                if (not(dx or dy) or not all(0<=q<n for q in v) or raw[v]):continue
                if dx and dy and (raw[u[0],v[1]] or raw[v[0],u[1]]):continue
                nd=d+math.hypot(dx,dy)*(c[u]+c[v])/2
                if nd < dist.get(v,float('inf')):dist[v]=nd;heapq.heappush(heap,(nd,v))
    assert np.isclose(result['cost'],dist[(8,2)]*.5)
    assert not plan_lab(z,raw,(5,2),(8,2))['success']
    assert not plan_lab(z,raw,(0,2),(8,2))['success']
    raw[5,:]=True; assert not plan_lab(z,raw,(2,2),(8,2))['success']
    raw[:]=False;raw[5,5]=True; expanded=obstacle_mask(raw,.5,.35)
    assert expanded[4,5] and not expanded[4,4] and not expanded[3,5]
    print('4 PASS: no raw obstacle contact/corner cuts; blocked starts and disconnected goals rejected; independent Dijkstra optimum; one 0.35m square-distance inflation')

def test_parity():
    from experiments.lab_baseline import run_case
    for case in [('08OB86_00294',100,False,[]),('08OB86_00294',200,True,[])]:
        result=run_case(case)
        assert len(result['audit']) == 38 and all(a['matched'] for a in result['audit'])
    print('5 PASS: task013 A*/TA*-S all non-energy path metrics and scenario identifiers match clean/debris, 100/200m; times independently remeasured')

if __name__=='__main__':
    for test in (test_geometry,test_unknown,test_navfn,test_paths,test_parity):test()
    print('all lab-geometry tests passed; requirement 6 is checked by the full conference/tests suite')
