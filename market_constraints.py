
import math
import pyomo.environ as pyo


def build_constraints(case):
    m = pyo.ConcreteModel()

    players = [g for g, gen in enumerate(case.gen) if gen.Pmax > 0]
    m.G = pyo.Set(initialize=players)
    m.x = pyo.Var(m.G)                                   # generator output, MW
    m.theta = pyo.Var([b.bus_i for b in case.bus])       # bus angle, rad
    m.f = pyo.Var(range(len(case.branch)))               # line flow, MW
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)

    # capacity constraints
    m.capacity = pyo.ConstraintList()
    for g in m.G:
        m.capacity.add((0, m.x[g], case.gen[g].Pmax))

    # network constraints
    m.flow = pyo.ConstraintList()
    m.angle = pyo.ConstraintList()
    m.line_capacity = pyo.ConstraintList()
    for l, br in enumerate(case.branch):
        diff = m.theta[br.fbus] - m.theta[br.tbus]
        if not br.status:
            m.flow.add(m.f[l] == 0)
            continue

        tap = br.ratio if br.ratio else 1.0
        susceptance = case.baseMVA / (br.x * tap)
        phase_shift = math.radians(br.angle)
        m.flow.add(
            m.f[l] == susceptance * (diff - phase_shift)
        ) # unit conversion
        m.angle.add((math.radians(br.angmin), diff, math.radians(br.angmax)))
        if br.rateA > 0:
            m.line_capacity.add((-br.rateA, m.f[l], br.rateA))


    # demand constraints
    m.demand = pyo.ConstraintList()
    for b, bus in enumerate(case.bus):
        # sum of generation at bus b - demand at bus b = sum of flows out of bus b - sum of flows into bus b
        gen_at_bus = [g for g in m.G if case.gen[g].bus == bus.bus_i]
        flow_into_bus = [l for l, br in enumerate(case.branch) if br.tbus == bus.bus_i]
        flow_out_of_bus = [l for l, br in enumerate(case.branch) if br.fbus == bus.bus_i]

        m.demand.add(
            sum(m.x[g] for g in gen_at_bus)
            - sum(m.f[l] for l in flow_out_of_bus)
            + sum(m.f[l] for l in flow_into_bus)
            == bus.Pd
        )



    return m
