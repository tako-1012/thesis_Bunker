#!/usr/bin/env python3
"""Aggregate TA* and Theta* 96-result JSONs into full_benchmark_results.json for analysis_and_report.py"""
import json
import os
BR = os.path.dirname(os.path.dirname(__file__))
BR = os.path.join(BR, 'benchmark_results')
ta = os.path.join(BR, 'ta_star_smoothed_96_results.json')
th = os.path.join(BR, 'theta_star_96_results.json')
out = os.path.join(BR, 'full_benchmark_results.json')
records = []
if os.path.exists(ta):
    with open(ta) as f:
        d = json.load(f)
        # ta file format is list of entries
        for r in d:
            r['planner'] = 'TA*'
            records.append(r)
if os.path.exists(th):
    with open(th) as f:
        d = json.load(f)
        for r in d:
            r['planner'] = 'Theta*'
            records.append(r)
with open(out, 'w') as f:
    json.dump(records, f, indent=2)
print('Wrote', out)
