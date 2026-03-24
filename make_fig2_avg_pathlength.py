#!/usr/bin/env python3
import matplotlib.pyplot as plt
import numpy as np
import os

# Values from latest analysis
algorithms = ['TA*', 'AHA*', 'FieldD*Hybrid', 'Theta*']
values = [21.27, 21.39, 23.60, 23.64]
colors = ['#8B4513', '#228B22', '#9370DB', '#FF4500']

os.makedirs('figures', exist_ok=True)

fig, ax = plt.subplots(figsize=(7,5))
indices = np.arange(len(algorithms))
bars = ax.bar(indices, values, color=colors, edgecolor='black', linewidth=0.8)

# Annotate values above bars
for bar, v in zip(bars, values):
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.3, f'{v:.2f} m', ha='center', va='bottom', fontsize=10, fontweight='bold')

ax.set_xticks(indices)
ax.set_xticklabels(algorithms, fontsize=11)
ax.set_ylabel('Average Path Length (m)', fontsize=12, fontweight='bold')
ax.set_title('Fig.2 Comparison of Average Path Length', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3)

# Caption text below figure
caption = ('TA*: 21.27 m (shortest), AHA*: 21.39 m, FieldD*Hybrid: 23.60 m, Theta*: 23.64 m')
plt.figtext(0.5, -0.05, caption, wrap=True, ha='center', fontsize=10)

plt.tight_layout()
png = 'figures/fig2_avg_path_length.png'
pdf = 'figures/fig2_avg_path_length.pdf'
plt.savefig(png, dpi=300, bbox_inches='tight')
plt.savefig(pdf, bbox_inches='tight')
print('Saved', png, pdf)
plt.close()
