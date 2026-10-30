
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


    # demand constraints
    m.demand = pyo.ConstraintList()
    for b, bus in enumerate(case.bus):
        # sum of generation at bus b - demand at bus b = sum of flows into bus b
        gen_at_bus = [g for g, gen in enumerate(case.gen) if gen.bus == bus.bus_i]
        flow_into_bus = [l for l, br in enumerate(case.branch) if br.tbus == bus.bus_i]
        flow_out_of_bus = [l for l, br in enumerate(case.branch) if br.fbus == bus.bus_i]

        m.demand.add(sum(m.x[g] for g in gen_at_bus) - bus.Pd == sum(m.f[l] for l in flow_into_bus) - sum(m.f[l] for l in flow_out_of_bus))



    return m
