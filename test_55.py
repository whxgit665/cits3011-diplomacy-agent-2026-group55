"""Reproducible experiments for group 55. Run beside the supplied game files.

Examples:
  PYTHONHASHSEED=0 python test_55.py --checks
  PYTHONHASHSEED=0 python test_55.py --variants all --repeats 10 --workers 4
  PYTHONHASHSEED=0 python test_55.py --variants no_coverage --seed 9000 --repeats 10
Only this experiment driver writes files. StudentAgent never writes files.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import sys
import time
import traceback

from diplomacy import Game
from agent_baselines import StaticAgent, RandomAgent, AttitudeAgent, GreedyAgent
from agent_55 import StudentAgent, VARIANTS
from game import run_one_game

POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']


class MeasuredAgent(StudentAgent):
    """Instrumentation outside the submitted agent; invalid orders fail loudly."""
    def __init__(self, variant):
        self.timings = defaultdict(list)
        self.order_count = 0
        t = time.perf_counter()
        super().__init__(variant=variant)
        self.timings['init'].append(time.perf_counter() - t)

    def new_game(self, game, power_name):
        t = time.perf_counter()
        super().new_game(game, power_name)
        self.timings['new_game'].append(time.perf_counter() - t)

    def update_game(self, orders):
        t = time.perf_counter()
        super().update_game(orders)
        self.timings['update_game'].append(time.perf_counter() - t)

    def get_actions(self):
        t = time.perf_counter()
        actions = super().get_actions()
        self.timings['get_actions'].append(time.perf_counter() - t)
        legal = self.game.get_all_possible_orders()
        own_locs = self.game.get_orderable_locations(self.power_name)
        allowed = {o for loc in own_locs for o in legal[loc]}
        assert all(o in allowed for o in actions), (self.game.get_current_phase(), actions, allowed)
        origins = [o.split()[1][:3] for o in actions]
        assert len(origins) == len(set(origins)), ('duplicate unit/province', actions)
        if self.game.phase_type == 'A':
            count = len(self.game.get_centers(self.power_name)) - len(self.game.get_units(self.power_name))
            assert len(actions) <= abs(count), ('too many adjustments', actions, count)
        self.order_count += len(actions)
        return actions


def one_case(case):
    variant, scenario, power, seed = case
    started = time.perf_counter()
    random.seed(seed)
    selector = random.Random(seed)
    pool = [RandomAgent, AttitudeAgent, AttitudeAgent, GreedyAgent, GreedyAgent]
    lineup = {p: StaticAgent if scenario == 1 else selector.choice(pool) for p in POWERS if p != power}
    row = {'variant': variant, 'scenario': scenario, 'power': power, 'seed': seed,
           'opponents': {p: cls.__name__ for p, cls in lineup.items()}}
    try:
        student = MeasuredAgent(variant)
        agents = {p: student if p == power else lineup[p]() for p in POWERS}
        result, year = run_one_game(agents)
        row.update(centres=min(18, result[power]), win=int(result[power] >= 18),
                   defeat=int(result[power] == 0), year=int(year),
                   orders=student.order_count,
                   max_seconds={k: max(v, default=0) for k, v in student.timings.items()},
                   action_seconds=student.timings['get_actions'], status='ok')
    except Exception:
        row.update(status='error', error=traceback.format_exc())
    # Whole worker high-water RSS, including interpreter, baselines and all
    # engine copies. This is NOT claimed to isolate the agent's own memory.
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    row['worker_peak_mb'] = rss / (1024 ** 2 if sys.platform == 'darwin' else 1024)
    row['elapsed_seconds'] = time.perf_counter() - started
    return row


def wilson(wins, n):
    if not n:
        return [0.0, 1.0]
    z, p = 1.96, wins / n
    centre = (p + z*z/(2*n)) / (1 + z*z/n)
    width = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [centre - width, centre + width]


def summarize(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['variant'], row['scenario']].append(row)
    summary = []
    for (variant, scenario), group in sorted(grouped.items()):
        good = [r for r in group if r['status'] == 'ok']
        n = len(good)
        centres = [r['centres'] for r in good]
        times = sorted(t for r in good for t in r['action_seconds'])
        wins = sum(r['win'] for r in good)
        summary.append({
            'variant': variant, 'scenario': scenario, 'games': n,
            'errors': len(group)-n, 'wins': wins, 'win_rate': wins/n if n else None,
            'win_95_wilson': wilson(wins, n),
            'mean_centres': statistics.mean(centres) if n else None,
            'sd_centres': statistics.stdev(centres) if n > 1 else 0,
            'max_action_seconds': max(times, default=0),
            'p95_action_seconds': times[min(len(times)-1, int(.95*len(times)))] if times else 0,
            'max_lifecycle_seconds': max((v for r in good for v in r['max_seconds'].values()), default=0),
            'max_worker_mb': max((r['worker_peak_mb'] for r in group), default=0),
            'per_power': {p: {
                'games': sum(r['power'] == p for r in good),
                'mean_centres': statistics.mean([r['centres'] for r in good if r['power'] == p])
                if any(r['power'] == p for r in good) else None,
                'wins': sum(r['win'] for r in good if r['power'] == p)} for p in POWERS}})
    return summary


def paired_differences(rows):
    """Exploratory paired-seed bootstrap; no multiple-comparison correction."""
    indexed = {(r['variant'], r['power'], r['seed']): r for r in rows
               if r['status'] == 'ok' and r['scenario'] == 2}
    rng = random.Random(55)
    result = {}
    for a, b in [('coverage', 'base'), ('coordination', 'base'), ('risk', 'base'),
                 ('full', 'no_coverage'), ('full', 'no_coordination'), ('full', 'no_risk'),
                 ('no_coverage', 'base'), ('no_coverage', 'coordination')]:
        differences = [r['centres'] - indexed[b, p, seed]['centres']
                       for (v, p, seed), r in indexed.items() if v == a and (b, p, seed) in indexed]
        if not differences:
            continue
        # Sort pairs for reproducibility regardless of worker completion order.
        differences.sort()
        samples = sorted(statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(5000))
        result[a + ' minus ' + b] = {'mean_sc_difference': statistics.mean(differences),
                                     'bootstrap_95': [samples[125], samples[4875]], 'n': len(differences)}
    return result


def checks():
    # All seven initial powers, every retained experimental configuration.
    for variant in VARIANTS:
        for power in POWERS:
            a = MeasuredAgent(variant)
            a.new_game(Game(), power)
            assert len(a.get_actions()) == len(a.game.get_units(power))
    def fixture(units, centres=None, phase='S1901M'):
        g = Game()
        g.clear_units()
        if centres is not None:
            g.clear_centers()
            for p, cs in centres.items():
                g.set_centers(p, cs)
        for p, us in units.items():
            g.set_units(p, us)
        g.set_current_phase(phase)
        return g
    # A single support bundle must break a held enemy centre.
    g = fixture({'FRANCE': ['A BUR', 'A RUH'], 'GERMANY': ['A MUN']},
                {'FRANCE': [c for c in Game().map.scs if c != 'MUN'], 'GERMANY': ['MUN']}, 'F1901M')
    a = MeasuredAgent('full'); a.new_game(g, 'FRANCE')
    orders = a.get_actions()
    assert any(' S ' in o for o in orders), orders
    g.set_orders('FRANCE', orders); g.process()
    assert 'A MUN' in g.get_units('FRANCE'), orders
    # A real convoy should let an otherwise isolated army cross the water.
    g = fixture({'ENGLAND': ['A LON', 'F NTH']},
                {'ENGLAND': ['LON', 'EDI', 'LVP']}, 'F1901M')
    a = MeasuredAgent('full'); a.new_game(g, 'ENGLAND')
    a._prepare(); a.route_cache = {}
    assert a._convoy_route('LON', 'BEL'), 'own-fleet convoy path missing'
    forced = ['A LON - BEL VIA', 'F NTH C A LON - BEL']
    assert all(o in g.get_all_possible_orders()[o.split()[1]] for o in forced)
    g.set_orders('ENGLAND', forced); g.process()
    assert 'A BEL' in g.get_units('ENGLAND')
    # Split coast does not provide an illegal shortcut between sea regions.
    assert not a.game.map.abuts('F', 'STP/SC', '-', 'BAR')
    assert a._distance('F', 'STP/SC', 'BAR') > 1
    # Multiple builds at one split-coast province must never be emitted.
    g = fixture({'RUSSIA': ['A WAR']},
                {'RUSSIA': ['WAR', 'MOS', 'SEV', 'STP', 'SWE']}, 'W1901A')
    a = MeasuredAgent('full'); a.new_game(g, 'RUSSIA')
    assert len(a.get_actions()) == 3
    # Required disbands and a genuine adjudicated retreat phase.
    g = fixture({'FRANCE': ['A PAR', 'A BUR', 'F BRE']}, {'FRANCE': ['PAR']}, 'W1901A')
    a = MeasuredAgent('full'); a.new_game(g, 'FRANCE')
    assert len(a.get_actions()) == 2
    g = fixture({'FRANCE': ['A BUR', 'A RUH'], 'GERMANY': ['A MUN']})
    g.set_orders('FRANCE', ['A BUR - MUN', 'A RUH S A BUR - MUN']); g.process()
    assert g.phase_type == 'R'
    a = MeasuredAgent('full'); a.new_game(g, 'GERMANY')
    assert len(a.get_actions()) == 1
    print('PASS: 56 opening/variant checks, supported capture, convoy, split coast, builds, disbands, retreat.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--checks', action='store_true')
    parser.add_argument('--variants', nargs='+', default=['no_coverage'])
    parser.add_argument('--scenarios', nargs='+', type=int, choices=[1, 2], default=[1, 2])
    parser.add_argument('--repeats', type=int, default=10)
    parser.add_argument('--seed', type=int, default=1000)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--output', default='results/experiment')
    args = parser.parse_args()
    if args.checks:
        checks(); return
    variants = list(VARIANTS) if args.variants == ['all'] else args.variants
    if any(v not in VARIANTS for v in variants) or args.repeats < 1 or args.workers < 1:
        parser.error('invalid variant/repeat/worker setting')
    prefix = Path(args.output)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    # Refuse overwrite so later experiments cannot silently replace evidence.
    raw = prefix.with_suffix('.jsonl')
    if raw.exists():
        parser.error(f'{raw} already exists; choose a new output prefix')
    cases = [(v, s, p, args.seed + r*100 + i) for v in variants for s in args.scenarios
             for r in range(args.repeats) for i, p in enumerate(POWERS)]
    metadata = {'python': sys.version, 'platform': platform.platform(), 'arguments': vars(args),
                'hash_seed': os.environ.get('PYTHONHASHSEED', 'unset'),
                'agent_sha256': hashlib.sha256(Path(__file__).with_name('agent_55.py').read_bytes()).hexdigest(),
                'note': 'Scenarios 1 and 2 only; no access to official Hidden Agent or tournament.'}
    prefix.with_suffix('.metadata.json').write_text(json.dumps(metadata, indent=2))
    rows = []
    with raw.open('w') as handle:
        if args.workers == 1:
            iterator = map(one_case, cases)
            executor = None
        else:
            executor = ProcessPoolExecutor(max_workers=args.workers)
            futures = [executor.submit(one_case, case) for case in cases]
            iterator = (f.result() for f in as_completed(futures))
        for row in iterator:
            rows.append(row)
            handle.write(json.dumps(row) + '\n'); handle.flush()
            if row['status'] != 'ok':
                print(row['error'], flush=True)
            if len(rows) % 14 == 0 or len(rows) == len(cases):
                print(f'{len(rows)}/{len(cases)} games complete', flush=True)
        if executor:
            executor.shutdown()
    summary = summarize(rows)
    prefix.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2))
    prefix.with_suffix('.paired.json').write_text(json.dumps(paired_differences(rows), indent=2))
    fields = ['variant', 'scenario', 'games', 'errors', 'wins', 'win_rate', 'mean_centres',
              'sd_centres', 'max_action_seconds', 'p95_action_seconds', 'max_lifecycle_seconds', 'max_worker_mb']
    with prefix.with_suffix('.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(summary)
    for r in summary:
        print(f"{r['variant']:16s} S{r['scenario']} n={r['games']:3d} errors={r['errors']} "
              f"SC={r['mean_centres'] or 0:.2f} wins={(r['win_rate'] or 0)*100:.1f}% "
              f"max={r['max_lifecycle_seconds']:.3f}s")
    if any(r['errors'] for r in summary):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
