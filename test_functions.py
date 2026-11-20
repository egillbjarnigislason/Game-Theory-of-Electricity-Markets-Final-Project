"""
Checks every function on tiny made-up markets where the answer can be worked out by hand.

Run with:  python3 test_functions.py

Cost and bid form used by the code:  a * x^2 + b * x
Market rule (KKT): every generator produces until  2 * a * x + b = price,  and supply = demand.
"""
import math

import pyomo.environ as pyo

from read_ieee_case import read_case, Case, Bus, Gen, GenCost, Branch
from market_constraints import build_constraints
import market_clear as mc
import finite_LP as flp
import separation_oracle as so
from golden_search import golden_search


results = []


def check(name, got, expected, tol=1e-3):
    ok = abs(got - expected) <= tol * max(1, abs(expected))
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: expected {expected:.4f}, got {got:.4f}")


# ---------- helpers to build tiny markets ----------

def bus(i, demand):
    return Bus(i, 1, demand, 0, 0, 0, 1, 1.0, 0.0, 1.0, 1, 1.06, 0.94)

def gen(at_bus, pmax):
    return Gen(at_bus, 0, 0, 0, 0, 1.0, 100, 1, pmax, 0)

def cost(c2, c1, c0=0.0):
    return GenCost(2, 0, 0, 3, [c2, c1, c0])

def line(from_bus, to_bus, x, limit):
    return Branch(from_bus, to_bus, 0, x, 0, limit, limit, limit, 0, 0, 1, -30, 30)

def one_bus_market(pmax1=100, pmax2=100, c0=0.0):
    """One bus, demand 30, generator 1 true cost 1 x^2 + c0, generator 2 true cost 2 x^2."""
    return Case("one_bus", "2", 100.0,
                bus=[bus(1, 30)],
                gen=[gen(1, pmax1), gen(1, pmax2)],
                gencost=[cost(1, 0, c0), cost(2, 0)],
                branch=[])

def two_bus_market(limit):
    """Cheap generator at bus 1, expensive generator and all demand (30) at bus 2, one line between them."""
    return Case("two_bus", "2", 100.0,
                bus=[bus(1, 0), bus(2, 30)],
                gen=[gen(1, 100), gen(2, 100)],
                gencost=[cost(1, 0), cost(2, 0)],
                branch=[line(1, 2, 0.1, limit)])

def clear(case, bids):
    m = build_constraints(case)
    mc.clear_market(case, m, bids)
    return m


print("\n1) read_ieee_case.py: read_case on the 14-bus file")
case14 = read_case("ieee data/pglib_opf_case14_ieee.m")
check("number of buses", len(case14.bus), 14)
check("number of generators", len(case14.gen), 5)
check("number of lines", len(case14.branch), 20)
check("total demand (MW)", sum(b.Pd for b in case14.bus), 259.0)
check("generator 1 linear cost c1", case14.gencost[0].params[1], 7.920951)
check("generator 1 capacity", case14.gen[0].Pmax, 340)


print("\n2) market_constraints.py: build_constraints keeps only generators that can produce")
m14 = build_constraints(case14)
check("players in the 14-bus case (SYNC units removed)", len(m14.G), 2)


print("\n3) market_clear.py, simple market: bids (1, 0) and (2, 0), demand 30")
# 2*1*x1 = 2*2*x2  ->  x1 = 2*x2  ->  x1 = 20, x2 = 10, price = 2*1*20 = 40
case = one_bus_market()
m = clear(case, ((1, 0), (2, 0)))
check("production generator 1", pyo.value(m.x[0]), 20)
check("production generator 2", pyo.value(m.x[1]), 10)
check("price", mc.get_prices(case, m)[1], 40)
# true costs 1*20^2 = 400 and 2*10^2 = 200
check("get_costs generator 1", mc.get_costs(case, m)[0], 400)
check("get_costs generator 2", mc.get_costs(case, m)[1], 200)
check("get_social_cost", mc.get_social_cost(case, m), 600)
# revenue = price * production = 800 and 400
check("get_revenues generator 1", mc.get_revenues(case, m)[0], 800)
check("get_revenues generator 2", mc.get_revenues(case, m)[1], 400)
# loss = true cost - revenue = -400 and -200 (negative = profit)
check("get_losses generator 1", mc.get_losses(case, m)[0], -400)
check("get_losses generator 2", mc.get_losses(case, m)[1], -200)


print("\n4) market_clear.py, with a linear part: bids (1, 10) and (1, 20), demand 30")
# 2*x1 + 10 = 2*x2 + 20  ->  x1 = x2 + 5  ->  x1 = 17.5, x2 = 12.5, price = 45
m = clear(case, ((1, 10), (1, 20)))
check("production generator 1", pyo.value(m.x[0]), 17.5)
check("production generator 2", pyo.value(m.x[1]), 12.5)
check("price", mc.get_prices(case, m)[1], 45)


print("\n5) market_clear.py, true cost with a fixed part c0 = 7: cost of generator 1 = 1*20^2 + 7")
case_c0 = one_bus_market(c0=7)
m = clear(case_c0, ((1, 0), (2, 0)))
check("get_costs generator 1", mc.get_costs(case_c0, m)[0], 407)


print("\n6) market_constraints.py, capacity limit: generator 1 can make at most 15")
# generator 1 stops at 15, generator 2 makes the other 15, price = 2*2*15 = 60
case_cap = one_bus_market(pmax1=15)
m = clear(case_cap, ((1, 0), (2, 0)))
check("production generator 1 (at its limit)", pyo.value(m.x[0]), 15)
check("production generator 2", pyo.value(m.x[1]), 15)
check("price", mc.get_prices(case_cap, m)[1], 60)


print("\n7) market_constraints.py, network without a line limit: same as test 3, one price everywhere")
case_net = two_bus_market(limit=0)       # rateA = 0 means no limit
m = clear(case_net, ((1, 0), (2, 0)))
check("production generator 1", pyo.value(m.x[0]), 20)
check("production generator 2", pyo.value(m.x[1]), 10)
check("power on the line from bus 1 to bus 2", pyo.value(m.f[0]), 20)
check("price at bus 1", mc.get_prices(case_net, m)[1], 40)
check("price at bus 2", mc.get_prices(case_net, m)[2], 40)


print("\n8) market_constraints.py, line limited to 10: bus 2 must make the rest itself, prices split")
# only 10 can travel, so x1 = 10, x2 = 20; price bus 1 = 2*1*10 = 20, bus 2 = 2*2*20 = 80
case_lim = two_bus_market(limit=10)
m = clear(case_lim, ((1, 0), (2, 0)))
check("production generator 1", pyo.value(m.x[0]), 10)
check("production generator 2", pyo.value(m.x[1]), 20)
check("power on the line", pyo.value(m.f[0]), 10)
check("price at bus 1", mc.get_prices(case_lim, m)[1], 20)
check("price at bus 2", mc.get_prices(case_lim, m)[2], 80)


print("\n9) Lemma 1: everyone multiplies their bid by 3 -> same production, 3 x the price")
m = clear(case, ((3, 0), (6, 0)))
check("production generator 1", pyo.value(m.x[0]), 20)
check("production generator 2", pyo.value(m.x[1]), 10)
check("price", mc.get_prices(case, m)[1], 120)


print("\n10) replace_action (finite_LP.py and separation_oracle.py)")
# player 1 switches to 2 x its true bid (5, 6) -> (10, 12), player 0 keeps (1, 2)
for name, func in (("finite_LP", flp.replace_action), ("separation_oracle", so.replace_action)):
    new = func(((1, 2), (3, 4)), 1, 2, (5, 6))
    check(f"{name}: player 0 unchanged, a", new[0][0], 1)
    check(f"{name}: player 1 now 2 x (5, 6), a", new[1][0], 10)
    check(f"{name}: player 1 now 2 x (5, 6), b", new[1][1], 12)


print("\n11) golden_search.py")
best_w, best_rho = golden_search(lambda w: (w - 1.3) ** 2 + 1.1, 0.5, 2.0)
check("valley with its bottom at 1.3: best omega", best_w, 1.3)
check("valley with its bottom at 1.3: lowest value", best_rho, 1.1)
best_w, _ = golden_search(lambda w: -w, 0.0, 1.0)
check("always going down: ends at the right edge", best_w, 1.0)


print("\n12) finite_LP.py, the example from the chat: C* = 100, two bid profiles")
# profile A: C = 110, gap = -20     profile B: C = 105, gap = +10
#   110 - 20 v <= 100 rho   and   105 + 10 v <= 100 rho   ->   v = 1/6, rho = 1.0667
# the gap is made to depend on omega: at omega = 2 it is A: -30, B: 0  ->  rho = 1.05
fake_case = Case("fake", "2", 100.0, gen=[gen(1, 100)])
A, B, TRUE = ((1.0, 0.0),), ((2.0, 0.0),), ((5.0, 0.0),)

def fake_C(a):
    return {A: 110.0, B: 105.0, TRUE: 100.0}[a]

def fake_c(a, i):
    first = pyo.value(a[0][0])
    if first == 1.0:
        return 20.0                      # loss with profile A
    if first == 2.0:
        return -10.0                     # loss with profile B
    omega = first / 5.0                  # deviated bid omega * 5
    return -10.0 * (omega - 1.0)         # loss after switching, changes with omega

lp = flp.create_finite_LP(fake_case, TRUE, fake_C, fake_c, [A, B])
rho, nu = flp.solve_finite_LP(lp, 1.0)
check("omega = 1: rho", rho, 1.0667)
check("omega = 1: nu", nu, 1 / 6)
rho, nu = flp.solve_finite_LP(lp, 2.0)
check("omega = 2: rho (the LP must recompute the gap for the new omega)", rho, 1.05)


print("\n13) separation_oracle.py: worst bid found by Gurobi vs. trying many bids by hand")
# one bus, demand 30, true costs 1 x^2 and 2 x^2, candidate rho = 1, nu = 0.5, omega = 1
case = one_bus_market()
min_a, max_a, min_b, max_b = 0.5, 5.0, 0.0, 20.0
a_true = ((1.0, 0.0), (2.0, 0.0))
p, v, w = 1.0, 0.5, 1.0

def clear_by_hand(bids, pmax=(100, 100), demand=30):
    """Find the price where supply equals demand, by halving the price range 100 times."""
    low, high = 0.0, 1e4
    for _ in range(100):
        price = (low + high) / 2
        x = [min(max((price - b) / (2 * a), 0), cap) for (a, b), cap in zip(bids, pmax)]
        low, high = (price, high) if sum(x) < demand else (low, price)
    return x, high

def true_cost(i, x):
    return a_true[i][0] * x ** 2 + a_true[i][1] * x

def violation(bids):
    x, price = clear_by_hand(bids)
    social = sum(true_cost(i, x[i]) for i in range(2))
    gap = 0
    for i in range(2):
        loss = true_cost(i, x[i]) - price * x[i]
        dev = list(bids); dev[i] = (w * a_true[i][0], w * a_true[i][1])
        xd, pd = clear_by_hand(dev)
        gap += (true_cost(i, xd[i]) - pd * xd[i]) - loss
    x_true, _ = clear_by_hand(a_true)
    best = sum(true_cost(i, x_true[i]) for i in range(2))
    return social + v * gap - p * best

grid_a = [min_a + k * (max_a - min_a) / 6 for k in range(7)]
grid_b = [min_b + k * (max_b - min_b) / 6 for k in range(7)]
by_hand = max(violation(((a1, b1), (a2, b2))) for a1 in grid_a for b1 in grid_b for a2 in grid_a for b2 in grid_b)

C_one = lambda bids: mc.get_social_cost(case, clear(case, bids))
oracle = so.create_separation_oracle(case, min_a, max_a, min_b, max_b, a_true, C_one, None)
bids, val = so.separation_oracle(oracle, p, v, w, epsilon=1e9)   # huge epsilon: solve all the way
check("the oracle's own number matches recomputing it by hand for its bid", violation(bids), val, tol=1e-2)
ok = val >= by_hand - 1e-2 * max(1, abs(by_hand))
results.append(ok)
print(f"  {'PASS' if ok else 'FAIL'}  the oracle finds at least as bad a bid as the best of {7**4} tried by hand: "
      f"oracle {val:.4f}, by hand {by_hand:.4f}")


print(f"\n{sum(results)} of {len(results)} checks passed")
