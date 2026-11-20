"""
Checks that the pieces WORK TOGETHER: golden search -> finite LP -> separation oracle -> back to the LP,
and that the final PoA bound is actually true.

Run with:  python3 test_pipeline.py

The tiny market: one bus, demand 30, two generators.
True costs: generator 1 = 1 x^2 + 5 x, generator 2 = 2 x^2 + 10 x.
Bids allowed: a in [0.5, 5], b in [0, 30]. Omega in [0.5, 2.5], so omega * true bid is always an allowed bid.
"""
import itertools
import subprocess
import sys

from read_ieee_case import Case, Bus, Gen, GenCost
from market_constraints import build_constraints
from golden_search import golden_search
import market_clear as mc
import finite_LP as flp
import separation_oracle as so
import discrete_bid_model as dbm


results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def bus(i, demand):
    return Bus(i, 1, demand, 0, 0, 0, 1, 1.0, 0.0, 1.0, 1, 1.06, 0.94)

def gen(at_bus, pmax):
    return Gen(at_bus, 0, 0, 0, 0, 1.0, 100, 1, pmax, 0)

def cost(c2, c1):
    return GenCost(2, 0, 0, 3, [c2, c1, 0.0])


case = Case("tiny", "2", 100.0, bus=[bus(1, 30)], gen=[gen(1, 100), gen(1, 100)],
            gencost=[cost(1, 5), cost(2, 10)], branch=[])
players = [0, 1]
a_star = ((1.0, 5.0), (2.0, 10.0))
min_a, max_a, min_b, max_b = 0.5, 5.0, 0.0, 30.0
omega_left, omega_right = 0.5, 2.5

# C and c exactly like main.py (with a cache so repeated bids are not cleared twice)
m = build_constraints(case)
cache = {}

def clear(a):
    if a not in cache:
        cleared = mc.clear_market(case, m, a)
        cache[a] = (mc.get_social_cost(case, cleared), mc.get_losses(case, cleared))
    return cache[a]

def C(a):
    return clear(a)[0]

def c(a, i):
    return clear(a)[1][i]

C_star = C(a_star)
epsilon = 1e-2 * C_star


print("\n1) The whole loop runs and stops with a certified bound")
H_start = [((1.5, 20.0), (0.6, 2.0)), ((4.0, 0.0), (4.0, 30.0)), ((0.5, 30.0), (5.0, 0.0))]
lp = flp.create_finite_LP(case, a_star, C, c, H_start)
oracle = so.create_separation_oracle(case, min_a, max_a, min_b, max_b, a_star, C, c)

rho_history, val = [], float("inf")
for k in range(1, 31):
    rho_of_omega = lambda x: flp.solve_finite_LP(lp, x)[0]
    w, _ = golden_search(rho_of_omega, omega_left, omega_right)
    p, v = flp.solve_finite_LP(lp, w)
    rho_history.append(p)
    new_a, val = so.separation_oracle(oracle, p, v, w, epsilon)
    print(f"     iteration {k}: omega = {w:.4f}, rho = {p:.4f}, nu = {v:.4f}, violation = {val:.4f}")
    if val <= epsilon:
        break
    flp.add_action_to_LP(lp, new_a, C, c, a_star)

bound = p + epsilon / C_star
check("the loop stops (violation below epsilon)", val <= epsilon, f"{k} iterations")
check("the bound is at least 1 (equilibrium can't beat the optimum)", bound >= 1 - 1e-6, f"bound = {bound:.4f}")


print("\n2) Golden search really picks a good omega")
samples = [omega_left + t * (omega_right - omega_left) / 20 for t in range(21)]
best_sampled = min(flp.solve_finite_LP(lp, x)[0] for x in samples)
p_check, _ = flp.solve_finite_LP(lp, w)
check("rho at the chosen omega is about as low as the best of 21 evenly spread omegas",
      p_check <= best_sampled + 1e-3, f"chosen {p_check:.4f}, best sampled {best_sampled:.4f}")
rho_values = [round(flp.solve_finite_LP(lp, x)[0], 6) for x in samples]
check("rho actually changes with omega (the LP is not ignoring omega)", len(set(rho_values)) > 1,
      f"from {min(rho_values):.4f} to {max(rho_values):.4f}")


print("\n3) Adding the oracle's bids only makes the LP stricter")
ups = all(rho_history[i + 1] >= rho_history[i] - 1e-3 for i in range(len(rho_history) - 1))
check("rho never goes down from one iteration to the next", ups, " -> ".join(f"{r:.4f}" for r in rho_history))


print("\n4) The final certificate holds for every bid on a grid (checked by brute force, no Gurobi)")
def clear_by_hand(bids, demand=30, pmax=100):
    low, high = 0.0, 1e4
    for _ in range(100):
        price = (low + high) / 2
        x = [min(max((price - bb) / (2 * aa), 0), pmax) for aa, bb in bids]
        low, high = (price, high) if sum(x) < demand else (low, price)
    costs = [a_star[i][0] * x[i] ** 2 + a_star[i][1] * x[i] for i in players]
    return sum(costs), [costs[i] - high * x[i] for i in players]

def switch(a, i, omega):
    a = list(a); a[i] = (omega * a_star[i][0], omega * a_star[i][1]); return tuple(a)

grid_a = [min_a + t * (max_a - min_a) / 6 for t in range(7)]
grid_b = [min_b + t * (max_b - min_b) / 6 for t in range(7)]
grid = [(aa, bb) for aa in grid_a for bb in grid_b]
worst = -float("inf")
for a in itertools.product(grid, repeat=2):
    cost_a, loss_a = clear_by_hand(a)
    gap = sum(clear_by_hand(switch(a, i, w))[1][i] - loss_a[i] for i in players)
    worst = max(worst, cost_a + v * gap - (p + epsilon / C_star) * C_star)
check("C(a) + nu * gap <= bound * C*  for all 2401 grid bids", worst <= 1e-3 * C_star, f"worst slack {worst:.4f} (must be <= 0)")


print("\n5) Every equilibrium we can find is inside the bound")
# each player may pick any grid bid, plus omega * own true bid (needed for the smoothness argument)
options = {i: grid + [(w * a_star[i][0], w * a_star[i][1])] for i in players}

def is_equilibrium(a):
    loss = clear_by_hand(a)[1]
    for i in players:
        for d in options[i]:
            a_dev = list(a); a_dev[i] = d
            if clear_by_hand(tuple(a_dev))[1][i] < loss[i] - 1e-6:
                return False
    return True

equilibria = [a for a in itertools.product(options[0], options[1]) if is_equilibrium(a)]
worst_eq = max((clear_by_hand(a)[0] / C_star for a in equilibria), default=None)
check("found at least one pure equilibrium on the grid", len(equilibria) > 0, f"{len(equilibria)} found")
if equilibria:
    check("worst equilibrium cost / C* <= PoA bound", worst_eq <= bound + 1e-6,
          f"worst equilibrium {worst_eq:.4f}, bound {bound:.4f}")


print("\n6) discrete_bid_model.py agrees with the rest")
actions = dbm.create_full_set_of_actions(case, 4, min_a, max_a, min_b, max_b)
check("number of joint actions = (4*4)^2", len(actions) == 256, f"{len(actions)}")
cce = dbm.create_discrete_cce_lp(case, actions, a_star, C, c)
grid4 = sorted({x for a in actions for x in a})
nash4 = []
for a in actions:
    loss = [c(a, i) for i in players]
    if all(c(tuple(d if j == i else a[j] for j in players), i) >= loss[i] - 1e-6 for i in players for d in grid4):
        nash4.append(C(a) / C_star)
check("CCE PoA >= 1", cce >= 1 - 1e-6, f"{cce:.4f}")
check("CCE PoA >= worst pure equilibrium on the same grid (a pure equilibrium is a CCE)",
      not nash4 or cce >= max(nash4) - 1e-6, f"CCE {cce:.4f}, worst pure {max(nash4) if nash4 else float('nan'):.4f}")


print("\n7) Player numbering: a SYNC unit (Pmax = 0) listed FIRST, like in the 57-bus file")
# every bid list has one bid per GENERATOR; the SYNC unit (generator 0) gets a placeholder the market ignores
case_sync = Case("sync_first", "2", 100.0, bus=[bus(1, 30)], gen=[gen(1, 0), gen(1, 100), gen(1, 100)],
                 gencost=[cost(0, 0), cost(1, 5), cost(2, 10)], branch=[])
a_star_sync = ((0.0, 0.0), (1.0, 5.0), (2.0, 10.0))
try:
    m_sync = build_constraints(case_sync)
    C_s = lambda a: mc.get_social_cost(case_sync, mc.clear_market(case_sync, m_sync, a))
    c_s = lambda a, i: mc.get_losses(case_sync, mc.clear_market(case_sync, m_sync, a))[i]
    # same market as the tiny one, just with an empty generator in front -> same optimal cost
    check("same optimal cost as the tiny market", abs(C_s(a_star_sync) - C_star) < 1e-3, f"{C_s(a_star_sync):.4f} vs {C_star:.4f}")
    lp_s = flp.create_finite_LP(case_sync, a_star_sync, C_s, c_s, [((0.001, 0.001),) + a for a in H_start])
    oracle_s = so.create_separation_oracle(case_sync, min_a, max_a, min_b, max_b, a_star_sync, C_s, c_s)
    p_s, v_s = flp.solve_finite_LP(lp_s, 1.0)
    p_t, v_t = flp.solve_finite_LP(lp, 1.0)
    new_s, val_s = so.separation_oracle(oracle_s, p_s, v_s, 1.0, 1e9)
    check("the oracle returns one bid per generator", len(new_s) == 3, f"{len(new_s)} bids")
    flp.add_action_to_LP(lp_s, new_s, C_s, c_s, a_star_sync)
    check("the LP, the oracle and the market all run with the SYNC unit first", True)
except Exception as e:
    check("the LP, the oracle and the market all run with the SYNC unit first", False, f"{type(e).__name__}: {e}")


print("\n8) main.py runs from start to end on the real 14-bus case (20 second limit)")
out = subprocess.run([sys.executable, "main.py", "ieee data/pglib_opf_case14_ieee.m", "20"],
                     capture_output=True, text=True)
lines = [l for l in out.stdout.splitlines() if "poa_bound" in l or "Time limit" in l]
check("main.py finishes without crashing", out.returncode == 0, out.stderr.strip().splitlines()[-1] if out.returncode else "")
check("main.py prints a PoA bound", any("poa_bound (under" in l for l in lines), "; ".join(lines))


print(f"\n{sum(results)} of {len(results)} checks passed")
