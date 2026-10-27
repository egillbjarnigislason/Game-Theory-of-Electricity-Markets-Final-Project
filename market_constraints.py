
import math
import pyomo.environ as pyo


def build_constraints(case):
    m = pyo.ConcreteModel()

    m.x = pyo.Var(range(len(case.gen)))                  # generator output, MW
    m.theta = pyo.Var([b.bus_i for b in case.bus])       # bus angle, rad
    m.f = pyo.Var(range(len(case.branch)))               # line flow, MW

    # capacity constraints
    m.capacity = pyo.ConstraintList()
    for g, gen in enumerate(case.gen):
        m.capacity.add((0, m.x[g], gen.Pmax))

    # network constraints
    m.flow = pyo.ConstraintList()
    m.angle = pyo.ConstraintList()
    for l, br in enumerate(case.branch):
        diff = m.theta[br.fbus] - m.theta[br.tbus]
        # phase angle constr
        m.flow.add(m.f[l] == case.baseMVA / br.x * diff) # unit conversion
        # max phase angle
        m.angle.add((math.radians(br.angmin), diff, math.radians(br.angmax)))






    return m
