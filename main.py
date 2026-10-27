
from read_ieee_case import read_case
from market_constraints import build_constraints

case = read_case("ieee data/pglib_opf_case14_ieee.m") 

print(case)

m = build_constraints(case)

m.pprint()