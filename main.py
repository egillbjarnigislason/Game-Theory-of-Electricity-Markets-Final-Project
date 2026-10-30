import time

from read_ieee_case import read_case
from market_constraints import build_constraints
from golden_search import golden_search
import market_clear as mc


ieee_file = "ieee data/pglib_opf_case14_ieee.m"
max_time_in_seconds = 1
accuracy = 10**-2
starting_H_subset_size = 10 


case = read_case(ieee_file) 

print(case)

m = build_constraints(case)

m.pprint()

# Each action is a tuple of (a, b) where a and b are the coefficients of the quadratic cost function for each generator.
# A joint action is a tuple of actions for all generators. For example, if there are 3 generators, a joint action could be ((a1, b1), (a2, b2), (a3, b3)).

# this m should have a function to get the social cost of a given action
# this m should have a function to get the loss for each player given a specific action


omega_left = 10**-5
omega_right = 1 # TODO upper bound for omega = (max price to bid / max cost)
H_subset = set() # TODO get random subset of the joint action space with specific size to reduce the number of constraints
a_star = None # TODO get a social optimal action
epsilon = 0 # TODO accuracy * C(a_star)
start_time = time.time()
val = float('inf')
k = 0
p = 1
v = 1

while epsilon < val and time.time() - start_time < max_time_in_seconds:

    rho_of_omega = None # TODO function to get the PoA bound of the LP for a given omega

    (w, p) = golden_search(rho_of_omega, omega_left, omega_right)
    v = None # TODO get the value of the LP for the given omega

    
    (new_a, val) = (None, 0) # TODO separation oracle

    H_subset.add(new_a)


    k += 1

if epsilon < val:
    print("epsilon < val")
    poa_bound = None # TODO p + epsilon / C(a_star)
    print("poa_bound: ", poa_bound)
else:
    print("Time limit reached")

print("Iterations: ", k)

