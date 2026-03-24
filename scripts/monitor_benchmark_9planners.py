#!/usr/bin/env python3
"""Monitor benchmark progress"""
import json, time
from collections import defaultdict

planners = ['A*', 'D*Lite', 'RRT*', 'HPA*', 'SAFETY', 'FieldD*Hybrid', 'TA*', 'MPAA*', 'Theta*']

while True:
    try:
        with open('benchmark_results/dataset3_9planners_results.json') as f:
            results = json.load(f)
        
        by_planner = defaultdict(int)
        for r in results:
            by_planner[r['planner']] += 1
        
        progress = len(results) / 810 * 100
        print(f'\n⏱  {time.strftime("%H:%M:%S")} | Progress: {len(results)}/810 ({progress:.1f}%)')
        
        for p in planners:
            c = by_planner.get(p, 0)
            bar = '█' * (c//3) + '░' * ((90-c)//3)
            status = '✓' if c >= 90 else f'{c}/90'
            print(f'  {p:20s} [{bar}] {status}')
        
        if len(results) >= 810:
            print('\n✓ BENCHMARK COMPLETE!')
            break
            
        time.sleep(30)
        
    except FileNotFoundError:
        print('Waiting for results file...')
        time.sleep(5)
    except KeyboardInterrupt:
        print('\n\nMonitoring stopped.')
        break
    except Exception as e:
        print(f'Error: {e}')
        time.sleep(10)
