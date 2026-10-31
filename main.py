import time
import random

from read_ieee_case import read_case
from market_constraints import build_constraints
from golden_search import golden_search
import market_clear as mc
import finite_LP as flp


ieee_file = "ieee data/pglib_opf_case14_ieee.m"
max_time_in_seconds = 1
accuracy = 10**-2
starting_H_subset_size = 10 


min_a = 0 # TODO what should the bounds actually be?
max_a = 10 # TODO what should the bounds actually be?
min_b = 0 # TODO what should the bounds actually be?
max_b = 10 # TODO what should the bounds actually be?



case = read_case(ieee_file) 

print(case)

m = build_constraints(case)

m.pprint()

# Each action is a tuple of (a, b) where a and b are the coefficients of the quadratic cost function for each generator.
# A joint action is a tuple of actions for all generators. For example, if there are 3 generators, a joint action could be ((a1, b1), (a2, b2), (a3, b3)).

def C(a):
    cleared_market = mc.clear_market(case, m, a)
    social_cost = mc.get_social_cost(case, cleared_market)
    return social_cost

def c(a, i):
    cleared_market = mc.clear_market(case, m, a)
    losses = mc.get_losses(case, cleared_market, a)
    return losses[i]

omega_left = 10**-5
omega_right = 1 # TODO upper bound for omega = (max price to bid / max cost)
H_subset = set([tuple([(random.uniform(min_a, max_a), random.uniform(min_b, max_b)) for _ in range(len(case.gen))]) for i in range(starting_H_subset_size)]) # TODO get random subset of the joint action space with specific size to reduce the number of constraints
a_star = tuple([tuple([case.gencost[g].params[-2], case.gencost[g].params[-1]]) for g in range(len(case.gen))])
epsilon = accuracy * C(a_star)
start_time = time.time()
val = float('inf')
k = 0
p = 1
v = 1
flpModel = flp.create_finite_LP(case, a_star, C, c, H_subset)

while epsilon < val and time.time() - start_time < max_time_in_seconds:

    rho_of_omega = lambda x: flp.solve_finite_LP(flpModel, x)[0]

    (w, p) = golden_search(rho_of_omega, omega_left, omega_right)
    v = flp.solve_finite_LP(flpModel, w)[1]

    
    (new_a, val) = (None, 0) # TODO separation oracle

    H_subset.add(new_a)
    flp.add_action_to_LP(flpModel, new_a, C, c, a_star)

    k += 1

if epsilon < val:
    print("epsilon < val")
    poa_bound = p + epsilon / C(a_star)
    print("poa_bound: ", poa_bound)
else:
    print("Time limit reached")

print("Iterations: ", k)

