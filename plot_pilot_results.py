"""Render standalone scientific figures from measured pilot artifacts."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent / 'results/pilot'
COLORS = {'coast': '#98a1ae', 'radial': '#a980ad', 'classical': '#b77938',
          'learned': '#5384b3', 'checked': '#287e76', 'hybrid': '#385044',
          'random_checked': '#ba6352'}
LABELS = {'coast': 'Coast', 'radial': 'Outward burn', 'classical': 'Classical search',
          'learned': 'Raw diffusion', 'checked': 'Checked diffusion',
          'hybrid': 'With fallback', 'random_checked': 'Checked random'}


def main():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.labelcolor': '#28313d', 'text.color': '#28313d',
                         'svg.hashsalt': 'powered-pilot'})
    summary = json.loads((ROOT / 'summary.json').read_text())
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), sharey=True, layout='constrained')
    for axis, split, title in zip(axes, ('test', 'stress'), ('Held-out launches', 'Closer launches: distribution shift')):
        rows = [g for g in summary['groups'] if g['split'] == split]
        y = np.arange(len(rows))
        values = np.array([g['success_fraction'] for g in rows])
        bounds = np.array([g['wilson_95'] for g in rows])
        axis.barh(y, values, color=[COLORS[g['controller']] for g in rows], height=.56)
        axis.errorbar(values, y, xerr=np.maximum(0, np.stack((values-bounds[:, 0], bounds[:, 1]-values))),
                      fmt='none', color='#28313d', capsize=3, lw=1)
        axis.set_yticks(y, [LABELS[g['controller']] for g in rows])
        axis.set_xlim(0, 1.17)
        axis.set_xticks([0, .25, .5, .75, 1], ['0%', '25%', '50%', '75%', '100%'])
        axis.set_title(title, loc='left', fontsize=12, pad=16)
        axis.set_xlabel('Flights reaching a state that escapes by coasting')
        axis.grid(axis='x', alpha=.12)
        for i, g in enumerate(rows):
            axis.text(1.07, i, f"{g['escaped']}/{g['flights']}", ha='center', va='center', fontsize=9)
    axes[0].invert_yaxis()
    fig.suptitle('Physics checks, learned proposals, and the classical baselines', x=.01, ha='left', fontsize=15)
    fig.savefig(ROOT / 'success.svg', bbox_inches='tight')
    plt.close(fig)

    witness = json.loads((ROOT / 'showcase.json').read_text())
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True, layout='constrained')
    for key in ('learned', 'checked'):
        flight = witness[key]
        points = np.array(flight['points'])
        color = COLORS[key]
        axes[0].plot(points[:, 0], points[:, 1], color=color, lw=2,
                     label=f"{LABELS[key]}: {flight['outcome'].replace('_', ' ')}")
        axes[1].plot(points[:, 0], 100*points[:, 7], color=color, lw=2)
        decisions = flight['decisions']
        axes[2].step([d['tau'] for d in decisions],
                     [np.linalg.norm(d['action']) for d in decisions],
                     where='post', color=color, alpha=.9, lw=1.4)
    axes[0].axhline(2, color='#161a20', lw=1, label='Event horizon, r = 2')
    axes[0].axhline(2.1, color='#ba6352', lw=1, ls=':', label='Mission safety cutoff, r = 2.1')
    axes[0].set_ylabel('Radius / M')
    axes[0].legend(loc='upper right', frameon=False, fontsize=9)
    axes[1].set_ylabel('Propellant remaining / %')
    axes[1].set_ylim(-3, 103)
    axes[2].set_ylabel('Commanded thrust / maximum')
    axes[2].set_ylim(-.03, 1.05)
    axes[2].set_xlabel('Ship proper time / M')
    for axis in axes:
        axis.grid(alpha=.15)
    fig.suptitle('One launch, two closed-loop decisions', x=.01, ha='left', fontsize=15)
    fig.savefig(ROOT / 'paired-flight.svg', bbox_inches='tight')
    plt.close(fig)
    print('Wrote results/pilot/success.svg and paired-flight.svg')


if __name__ == '__main__':
    main()
