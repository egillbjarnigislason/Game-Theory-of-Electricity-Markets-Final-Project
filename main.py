import sys
import time
import random

from read_ieee_case import read_case
from market_constraints import build_constraints
from golden_search import golden_search
import discrete_bid_model as dbm
import market_clear as mc
import finite_LP as flp
import separation_oracle as so


# usage: python main.py [case file] [time limit in seconds]   (defaults below are used if not given)
ieee_file = sys.argv[1] if len(sys.argv) > 1 else "ieee data/pglib_opf_case14_ieee.m"
max_time_in_seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 200
accuracy = 10**-2
starting_H_subset_size = 10 
minimum_bid_val = 10**-3
max_coefficient_for_bid = 10
num_steps_for_discrete_bid = 5


case = read_case(ieee_file) 

players = [g for g, gen in enumerate(case.gen) if gen.Pmax > 0]
min_a = minimum_bid_val
max_a = max(0.7, max_coefficient_for_bid * max([case.gencost[g].params[-3] for g in players]))
min_b = minimum_bid_val
max_b = max(120, max_coefficient_for_bid * max([case.gencost[g].params[-2] for g in players]))

#print(case)

m = build_constraints(case)

#m.pprint()

# Each action is a tuple of (a, b) where a and b are the coefficients of the quadratic cost function for each generator.
# A joint action is a tuple of actions for all generators. For example, if there are 3 generators, a joint action could be ((a1, b1), (a2, b2), (a3, b3)).

social_cost_cache = {}
losses_cache = {}

def C(a):
    if a in social_cost_cache:
        return social_cost_cache[a]
    else:
        cleared_market = mc.clear_market(case, m, a)
        social_cost = mc.get_social_cost(case, cleared_market)
        social_cost_cache[a] = social_cost
        losses = mc.get_losses(case, cleared_market)
        losses_cache[a] = losses

        return social_cost

def c(a, i):
    if a in losses_cache:
        return losses_cache[a][i]
    else:
        cleared_market = mc.clear_market(case, m, a)
        losses = mc.get_losses(case, cleared_market)
        losses_cache[a] = losses
        social_cost = mc.get_social_cost(case, cleared_market)
        social_cost_cache[a] = social_cost
        return losses[i]

# calculate the lower bound for omega such that omega multiplied with all the true coefficients of the generators is still an allowed bid
# omega_left * min(a) = min_a => omega_left = min_a / min(a)
# omega_left = max(min_a / min([case.gencost[g].params[-3] for g in players]), min_b / min([case.gencost[g].params[-2] for g in players]))
omega_left = min_b / min([case.gencost[g].params[-2] for g in players if case.gencost[g].params[-2] > 0])


# calculate the upper bound for omega such that omega multiplied with all the true coefficients of the generators is still an allowed bid
# omega_right * max(a) = max_a => omega_right = max_a / max(a)
#omega_right = min(max_a / max([case.gencost[g].params[-3] for g in players]), max_b / max([case.gencost[g].params[-2] for g in players]))
omega_right = max_b / max([case.gencost[g].params[-2] for g in players if case.gencost[g].params[-2] > 0])


H_subset = set([tuple([(random.uniform(min_a, max_a), random.uniform(min_b, max_b)) for _ in players]) for i in range(starting_H_subset_size)])
a_star = tuple([tuple([case.gencost[g].params[-3], case.gencost[g].params[-2]]) for g in players])
epsilon = accuracy * C(a_star)
val = float('inf')
k = 0
p = 1
v = 1
flpModel = flp.create_finite_LP(case, a_star, C, c, H_subset)
separation_oracle_model = so.create_separation_oracle(case, min_a, max_a, min_b, max_b, a_star, C, c)
start_time = time.time()

while epsilon < val and time.time() - start_time < max_time_in_seconds:
    k += 1
    print("Iteration: ", k)

    rho_of_omega = lambda x: flp.solve_finite_LP(flpModel, x)[0]

    (w, p) = golden_search(rho_of_omega, omega_left, omega_right)
    (p, v) = flp.solve_finite_LP(flpModel, w)

    (new_a, val) = so.separation_oracle(separation_oracle_model, p, v, w, epsilon)
    print("Val: ", val)

    H_subset.add(new_a)
    flp.add_action_to_LP(flpModel, new_a, C, c, a_star)

if val <= epsilon:
    poa_bound = p + epsilon / C(a_star)
    print("poa_bound (under configured nodal-price bounds): ", poa_bound)
else:
    print("Time limit reached before convergence; no PoA bound is certified.")

print("Iterations: ", k)



full_set_of_actions = dbm.create_full_set_of_actions(case, num_steps_for_discrete_bid, min_a, max_a, min_b, max_b)
print("Number of joint actions in the discrete bid set: ", len(full_set_of_actions))

p = dbm.create_discrete_cce_lp(case, full_set_of_actions, a_star, C, c)


print("CCE poa_bound (under discrete bid set): ", p)
