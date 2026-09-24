"""CITS3011 group 55: bounded heuristic search for No-Press Diplomacy.

Original implementation developed with disclosed Codex assistance.
Basic method: beam search over joint move/hold orders with a distance heuristic.
G: diminishing-return global target coverage.
C: atomic support/convoy bundles and local joint-plan improvement.
R: observed opponent mobility, destination risk and centre defence.
All variants remain executable through the ``variant`` constructor argument.
Only the supplied Agent interface and the game engine are used; no baseline
decision procedure is imported, copied or called.
"""

from collections import defaultdict, deque
from itertools import combinations
import time
import timeout_decorator
from agent_baselines import Agent


VARIANTS = {
    'base': (False, False, False),
    'coverage': (True, False, False),
    'coordination': (False, True, False),
    'risk': (False, False, True),
    'no_coverage': (False, True, True),
    'no_coordination': (True, False, True),
    'no_risk': (True, True, False),
    'full': (True, True, True),
}


def province(loc):
    return loc[:3]


class StudentAgent(Agent):
    @timeout_decorator.timeout(1)
    def __init__(self, agent_name='Harbour', variant='no_coverage'):
        super().__init__(agent_name)
        self.coverage, self.coordination, self.risk = VARIANTS[variant]
        self.variant = variant
        self.beam_width = 10
        self.mobility = {}

    @timeout_decorator.timeout(1)
    def new_game(self, game, power_name):
        self.game, self.power_name = game, power_name
        self.mobility = {p: [2.0, 2.0] for p in game.powers}
        # Separate coast-aware movement graphs; BFS distances are a relaxed
        # problem ignoring occupation, support and future opponents' orders.
        self.distances = {}
        self.nodes = {}
        for kind in ('A', 'F'):
            nodes = sorted({loc.upper() for loc, typ in game.map.loc_type.items()
                            if (kind == 'A' and typ in ('LAND', 'COAST') and '/' not in loc)
                            or (kind == 'F' and typ in ('WATER', 'COAST')
                                and loc == loc.upper())})
            self.nodes[kind] = nodes
            adjacent = {a: [b for b in nodes if game.map.abuts(kind, a, '-', b)]
                        for a in nodes}
            for start in nodes:
                distances = {start: 0}
                queue = deque([start])
                while queue:
                    a = queue.popleft()
                    for b in adjacent[a]:
                        if b not in distances:
                            distances[b] = distances[a] + 1
                            queue.append(b)
                # A fleet's distance to a split-coast province is the minimum
                # over its reachable coasts, not an edge joining the coasts.
                for loc, distance in list(distances.items()):
                    base = province(loc)
                    distances[base] = min(distances.get(base, 99), distance)
                self.distances[kind, start] = distances

    @timeout_decorator.timeout(1)
    def update_game(self, all_power_orders):
        if self.game.phase_type == 'M':
            for p, power in self.game.powers.items():
                orders = {o.split()[1][:3]: o.split() for o in all_power_orders.get(p, [])
                          if len(o.split()) >= 3}
                moved = sum(orders.get(u.split()[1][:3], ['', '', 'H'])[2] == '-'
                            for u in power.units if not u.startswith('*'))
                total = sum(not u.startswith('*') for u in power.units)
                a, b = self.mobility[p]
                # Discounted counts allow behaviour to change within a game.
                self.mobility[p] = [2 + .85 * (a - 2) + moved,
                                    2 + .85 * (b - 2) + total - moved]
        # The supplied state synchronization protocol is preserved.
        for power_name in all_power_orders.keys():
            self.game.set_orders(power_name, all_power_orders[power_name])
        self.game.process()

    def _distance(self, kind, loc, target):
        return self.distances.get((kind, loc), {}).get(province(target), 99)

    def _prepare(self):
        self.legal = self.game.get_all_possible_orders()
        self.own_centres = set(self.game.get_centers(self.power_name))
        self.targets = sorted(set(self.game.map.scs) - self.own_centres)
        self.units = sorted(u for u in self.game.get_units(self.power_name)
                            if not u.startswith('*'))
        self.index = {province(u.split()[1]): i for i, u in enumerate(self.units)}
        self.occupants = {}
        self.enemy_moves = defaultdict(list)
        self.enemy_support = defaultdict(set)
        for p, power in self.game.powers.items():
            for unit in power.units:
                if unit.startswith('*'):
                    continue
                kind, loc = unit.split()
                self.occupants[province(loc)] = (p, unit)
                if p == self.power_name:
                    continue
                possibilities = self.legal.get(province(loc), [])
                destinations = sorted({province(o.split()[3]) for o in possibilities
                                       if o.startswith(unit + ' - ') and ' VIA' not in o})
                a, b = self.mobility[p]
                moving = a / (a + b) if self.risk else .5
                weights = {d: 1.0 + 3.0 * (d in self.game.map.scs
                                          and d not in power.centers)
                           for d in destinations}
                total = sum(weights.values()) or 1
                for dest in destinations:
                    self.enemy_moves[dest].append((loc[:3], p, moving * weights[dest] / total))
                for o in possibilities:
                    words = o.split()
                    if len(words) >= 5 and words[2] == 'S':
                        self.enemy_support[province(words[-1])].add((loc[:3], p))
        self.fall = self.game.get_current_phase().startswith('F')
        self.value_cache = {}
        self.feature_cache = {}

    def _features(self, kind, loc):
        key = kind, loc
        if key not in self.feature_cache:
            self.feature_cache[key] = tuple(1.0 / (1 + self._distance(kind, loc, t)) ** 2
                                            for t in self.targets)
        return self.feature_cache[key]

    def _value(self, kind, loc):
        key = kind, loc
        if key not in self.value_cache:
            values = sorted(self._features(kind, loc), reverse=True)
            # Immediate SC occupancy dominates travel potential; ownership
            # changes only after autumn, so an uncaptured SC remains a target.
            self.value_cache[key] = (10.0 if province(loc) in self.targets else 0.0) + (
                5.0 * sum(values[:2]))
        return self.value_cache[key]

    def _score(self, plan):
        """Cheap approximate joint outcome; not a full Diplomacy adjudicator."""
        words = [o.split() for o in plan]
        destinations = [province(w[3]) if w[2] == '-' else province(w[1]) for w in words]
        moving_to = defaultdict(list)
        supports = defaultdict(float)
        for i, w in enumerate(words):
            if w[2] == '-':
                moving_to[destinations[i]].append(i)
            elif w[2] == 'S':
                target_i = self.index.get(province(w[4]))
                if target_i is None:
                    continue
                supported = words[target_i]
                matching = (len(w) == 7 and supported[2] == '-'
                            and province(w[6]) == destinations[target_i]) or (
                                len(w) == 5 and supported[2] != '-')
                if matching:
                    cut = sum(x[2] for x in self.enemy_moves[province(w[1])]
                              if x[0] != destinations[target_i]) if self.risk else 0
                    supports[target_i] += max(.3, 1.0 - cut)
        chances = [1.0] * len(plan)
        for i, w in enumerate(words):
            if w[2] != '-':
                continue
            dest = destinations[i]
            if len(moving_to[dest]) > 1:
                chances[i] = 0.0
                continue
            strength = 1 + supports[i]
            occupant = self.occupants.get(dest)
            if occupant and occupant[0] != self.power_name:
                a, b = self.mobility[occupant[0]]
                stays = b / (a + b) if self.risk else .85
                chances[i] = .98 if strength > 1.35 else .65 * (1 - stays)
                if self.risk and strength > 1.35:
                    helpers = sum(1 for _, p in self.enemy_support[dest] if p == occupant[0])
                    chances[i] *= max(.65, 1 - .08 * helpers)
            if self.risk:
                contest = sum(x[2] for x in self.enemy_moves[dest]
                              if not occupant or x[0] != province(occupant[1].split()[1]))
                chances[i] *= max(.25, 1 - contest / strength ** 2)
            if 'VIA' in w:
                route = self._convoy_route(w[1], w[3])
                if not route or any(plan[j] != f'{self.units[j]} C A {w[1]} - {w[3]}' for j in route):
                    chances[i] = 0
        # Resolve own occupancy chains approximately, including head-to-head
        # swaps. Direct rotations of >=3 units are allowed by Diplomacy.
        for _ in range(2):
            for i, w in enumerate(words):
                if w[2] != '-':
                    continue
                j = self.index.get(destinations[i])
                if j is not None:
                    if words[j][2] != '-' or (destinations[j] == province(w[1])
                                              and 'VIA' not in w and 'VIA' not in words[j]):
                        chances[i] = 0
                    else:
                        chances[i] = min(chances[i], chances[j])
        score = 0.0
        covered = [0.0] * len(self.targets)
        protected = defaultdict(float)
        for i, w in enumerate(words):
            kind, src = w[:2]
            dest = w[3] if w[2] == '-' else src
            chance = chances[i]
            before, after = self._value(kind, src), self._value(kind, dest)
            score += (0.5 if self.coverage else 1.0) * ((1 - chance) * before + chance * after)
            if w[2] == '-':
                score -= .12 + .6 * (1 - chance)
            if self.coverage:
                src_features, dst_features = self._features(kind, src), self._features(kind, dest)
                for t in range(len(covered)):
                    covered[t] = max(covered[t], chance * dst_features[t] + (1 - chance) * src_features[t])
            protected[province(src)] += (1 - chance if w[2] == '-' else 1) * (1 + supports[i])
            if w[2] == '-':
                protected[province(dest)] += chance
            if self.risk:
                # Value surviving units and penalize exposed stationary units.
                danger = sum(x[2] for x in self.enemy_moves[province(dest)])
                score -= .7 * chance * max(0.0, danger - .5 * supports[i])
        if self.coverage:
            score += 9.0 * sum(covered)
        if self.risk:
            for centre in self.own_centres:
                danger = sum(x[2] for x in self.enemy_moves[centre])
                occupant = self.occupants.get(centre)
                if occupant and occupant[0] != self.power_name:
                    danger += .9
                score -= (10 if self.fall else 4) * min(1.0, danger) / (1 + 4 * protected[centre])
        return score

    def _convoy_route(self, source, destination):
        key = source, destination
        if key in self.route_cache:
            return self.route_cache[key]
        available = [i for i, u in enumerate(self.units) if u.startswith('F ')
                     and f'{u} C A {source} - {destination}' in self.legal.get(province(u.split()[1]), [])]
        queue = deque((i, [i]) for i in available
                      if self.game.map.abuts('F', self.units[i].split()[1], 'S', source))
        seen = {i for i, _ in queue}
        while queue:
            i, path = queue.popleft()
            loc = self.units[i].split()[1]
            if self.game.map.abuts('F', loc, 'S', destination):
                self.route_cache[key] = path
                return path
            for j in available:
                if j not in seen and self.game.map.abuts('F', loc, '-', self.units[j].split()[1]):
                    seen.add(j)
                    queue.append((j, path + [j]))
        self.route_cache[key] = []
        return []

    def _movement(self, deadline):
        self.route_cache = {}
        holds = [u + ' H' for u in self.units]
        options = []
        for unit in self.units:
            orders = [o for o in self.legal[province(unit.split()[1])]
                      if o.startswith(unit + ' - ') and ' VIA' not in o]
            orders.sort(key=lambda o: (-self._value(unit[0], o.split()[3]), o))
            options.append([unit + ' H'] + orders[:7])
        # Bounded beam: state = one complete plan with a progressively fixed
        # prefix; suffix units hold until expanded. This is not multi-ply search.
        beam = [(self._score(holds), holds)]
        for i, orders in enumerate(options):
            expanded = []
            for _, plan in beam:
                for order in orders:
                    candidate = plan[:]
                    candidate[i] = order
                    expanded.append((self._score(candidate), candidate))
            expanded.sort(key=lambda x: (-x[0], x[1]))
            beam = expanded[:self.beam_width]
            if time.perf_counter() >= deadline:
                break
        best_score, best = beam[0]
        if not self.coordination:
            return best
        # Atomic bundles cross the local-search barrier where an unsupported
        # attack and an isolated support are each inferior to holding.
        bundles = []
        for i, unit in enumerate(self.units):
            for order in options[i]:
                w = order.split()
                supporters = []
                for j, helper in enumerate(self.units):
                    if j == i:
                        continue
                    support = f'{helper} S {unit}' + (f' - {w[3]}' if w[2] == '-' else '')
                    if support in self.legal[province(helper.split()[1])]:
                        supporters.append((j, support))
                bundles.append({i: order})
                for j, support in supporters:
                    bundles.append({i: order, j: support})
                for (j, a), (k, b) in combinations(supporters[:5], 2):
                    bundles.append({i: order, j: a, k: b})
            if unit.startswith('A '):
                for order in sorted(self.legal[province(unit.split()[1])]):
                    if order.startswith(unit + ' - ') and order.endswith(' VIA'):
                        w = order.split()
                        route = self._convoy_route(w[1], w[3])
                        if route:
                            bundle = {i: order}
                            bundle.update({j: f'{self.units[j]} C A {w[1]} - {w[3]}' for j in route})
                            bundles.append(bundle)
        for _ in range(3):
            old_score = best_score
            chosen = best
            for bundle in bundles:
                candidate = best[:]
                for i, order in bundle.items():
                    candidate[i] = order
                score = self._score(candidate)
                if score > best_score + 1e-8:
                    best_score, chosen = score, candidate
                if time.perf_counter() >= deadline:
                    return chosen
            best = chosen
            if best_score <= old_score + 1e-8:
                break
        return best

    def _retreat(self):
        result, used = [], set()
        for loc in sorted(self.game.get_orderable_locations(self.power_name)):
            candidates = [o for o in self.legal[loc] if ' R ' in o and province(o.split()[3]) not in used]
            if candidates:
                best = max(candidates, key=lambda o: (self._value(o[0], o.split()[3]), o))
                result.append(best)
                used.add(province(best.split()[3]))
            else:
                disbands = [o for o in self.legal[loc] if o.endswith(' D')]
                if disbands:
                    result.append(sorted(disbands)[0])
        return result

    def _adjust(self):
        count = len(self.own_centres) - len(self.units)
        candidates = sorted({o for loc in self.game.get_orderable_locations(self.power_name)
                             for o in self.legal[loc] if o.endswith(' B') or o.endswith(' D')})
        if count < 0:
            return sorted((o for o in candidates if o.endswith(' D')),
                          key=lambda o: (self._value(o[0], o.split()[1]), o))[: -count]
        result, built = [], set()
        projected = self.units[:]
        for _ in range(count):
            options = [o for o in candidates if o.endswith(' B') and province(o.split()[1]) not in built]
            if not options:
                break
            def build_value(order):
                kind, loc = order.split()[:2]
                features = self._features(kind, loc)
                redundancy = []
                for t in self.targets:
                    redundancy.append(min((self._distance(u[0], u.split()[1], t) for u in projected), default=99))
                value = sum(features[j] * (1.0 if self._distance(kind, loc, t) < redundancy[j] else .2)
                            for j, t in enumerate(self.targets))
                # Fleet capability is needed to leave Great Britain; this
                # follows map reachability rather than a country opening book.
                reachable = sum(self._distance(kind, loc, t) < 99 for t in self.targets)
                return value + .01 * reachable
            best = max(options, key=lambda o: (build_value(o), o))
            result.append(best)
            built.add(province(best.split()[1]))
            projected.append(' '.join(best.split()[:2]))
        return result

    @timeout_decorator.timeout(1)
    def get_actions(self):
        deadline = time.perf_counter() + .60
        self._prepare()
        if self.game.phase_type == 'R':
            return self._retreat()
        if self.game.phase_type == 'A':
            return self._adjust()
        if not self.units or self.game.phase_type != 'M':
            return []
        return self._movement(deadline)
