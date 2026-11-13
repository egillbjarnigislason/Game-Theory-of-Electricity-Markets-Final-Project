import math

import pyomo.environ as pyo


def replace_action(a, i, w, a_i_true):
    new_a = list(a)
    new_a[i] = tuple(w * value for value in a_i_true)
    return tuple(new_a)


def _load_solver_solution(model, results):
    if not results.solution:
        return False

    status = results.solver.status
    if status == pyo.SolverStatus.aborted:
        # This incumbent is intentionally accepted when it satisfies BestObjStop.
        results.solver.status = pyo.SolverStatus.ok
    try:
        model.solutions.load_from(results)
    finally:
        results.solver.status = status
    return True


def runModel(model, addprint=False, BestObjStop=None):
    solver = pyo.SolverFactory("gurobi")
    if not solver.available():
        raise RuntimeError("Gurobi solver is not available in your environment.")

    solver.options["NonConvex"] = 2
    if BestObjStop is not None:
        solver.options["BestObjStop"] = BestObjStop

    results = solver.solve(model, tee=addprint, load_solutions=False)
    has_solution = _load_solver_solution(model, results)
    termination = results.solver.termination_condition
    if termination == pyo.TerminationCondition.optimal:
        if not has_solution:
            raise RuntimeError(
                "Optimal separation oracle solve returned no solution."
            )
        return model
    incumbent = (
        pyo.value(model.objective, exception=False) if has_solution else None
    )
    if (
        BestObjStop is not None
        and incumbent is not None
        and incumbent > BestObjStop
    ):
        return model
    if BestObjStop is not None:
        solver.options.pop("BestObjStop", None)
        results = solver.solve(model, tee=addprint, load_solutions=False)
        termination = results.solver.termination_condition
        if termination == pyo.TerminationCondition.optimal:
            if not _load_solver_solution(model, results):
                raise RuntimeError(
                    "Optimal separation oracle solve returned no solution."
                )
            return model
    raise RuntimeError(
        f"Separation oracle solve failed: {termination}. Check the KKT model."
    )


def create_separation_oracle(
    case, min_a, max_a, min_b, max_b, a_true, C, _c
):
    model = pyo.ConcreteModel()

    model.generators = pyo.RangeSet(0, len(case.gen) - 1)
    active_generators = [
        g for g, generator in enumerate(case.gen) if generator.Pmax > 0
    ]
    model.G = pyo.Set(initialize=active_generators)
    model.buses = pyo.Set(initialize=[bus.bus_i for bus in case.bus])
    model.lines = pyo.RangeSet(0, len(case.branch) - 1)
    active_lines = [
        l for l, branch in enumerate(case.branch) if branch.status
    ]
    model.active_lines = pyo.Set(initialize=active_lines)
    model.limited_lines = pyo.Set(
        initialize=[
            l for l in active_lines if case.branch[l].rateA > 0
        ]
    )
    model.scenarios = pyo.RangeSet(0, len(case.gen))

    model.p = pyo.Param(initialize=1.0, mutable=True)
    model.v = pyo.Param(initialize=1.0, mutable=True)
    model.w = pyo.Param(initialize=1.0, mutable=True)
    model.inactive_bid_a = pyo.Param(initialize=min_a)
    model.inactive_bid_b = pyo.Param(initialize=min_b)

    total_demand = sum(bus.Pd for bus in case.bus)
    # This user-selected price range bounds otherwise non-unique KKT duals.
    price_cap = 2 * max_a * total_demand + max_b

    model.bid_a = pyo.Var(
        model.G,
        domain=pyo.NonNegativeReals,
        bounds=(min_a, max_a),
    )
    model.bid_b = pyo.Var(
        model.G,
        domain=pyo.NonNegativeReals,
        bounds=(min_b, max_b),
    )
    model.dispatch = pyo.Block(model.scenarios)

    generators_at_bus = {
        bus.bus_i: [
            g for g in active_generators if case.gen[g].bus == bus.bus_i
        ]
        for bus in case.bus
    }
    lines_from_bus = {
        bus.bus_i: [
            l for l, branch in enumerate(case.branch) if branch.fbus == bus.bus_i
        ]
        for bus in case.bus
    }
    lines_to_bus = {
        bus.bus_i: [
            l for l, branch in enumerate(case.branch) if branch.tbus == bus.bus_i
        ]
        for bus in case.bus
    }

    for scenario in model.scenarios:
        dispatch = model.dispatch[scenario]
        dispatch.x = pyo.Var(model.G, domain=pyo.Reals)
        dispatch.theta = pyo.Var(model.buses, domain=pyo.Reals)
        dispatch.f = pyo.Var(model.lines, domain=pyo.Reals)
        dispatch.lmp = pyo.Var(
            model.buses, domain=pyo.NonNegativeReals, bounds=(0, price_cap)
        )
        dispatch.flow_dual = pyo.Var(model.lines, domain=pyo.Reals)
        dispatch.capacity_lower_dual = pyo.Var(
            model.G, domain=pyo.NonNegativeReals
        )
        dispatch.capacity_upper_dual = pyo.Var(
            model.G, domain=pyo.NonNegativeReals
        )
        dispatch.angle_lower_dual = pyo.Var(
            model.active_lines, domain=pyo.NonNegativeReals
        )
        dispatch.angle_upper_dual = pyo.Var(
            model.active_lines, domain=pyo.NonNegativeReals
        )
        dispatch.flow_lower_dual = pyo.Var(
            model.limited_lines, domain=pyo.NonNegativeReals
        )
        dispatch.flow_upper_dual = pyo.Var(
            model.limited_lines, domain=pyo.NonNegativeReals
        )
        dispatch.capacity_lower_slack = pyo.Var(
            model.G, domain=pyo.NonNegativeReals
        )
        dispatch.capacity_upper_slack = pyo.Var(
            model.G, domain=pyo.NonNegativeReals
        )
        dispatch.angle_lower_slack = pyo.Var(
            model.active_lines, domain=pyo.NonNegativeReals
        )
        dispatch.angle_upper_slack = pyo.Var(
            model.active_lines, domain=pyo.NonNegativeReals
        )
        dispatch.flow_lower_slack = pyo.Var(
            model.limited_lines, domain=pyo.NonNegativeReals
        )
        dispatch.flow_upper_slack = pyo.Var(
            model.limited_lines, domain=pyo.NonNegativeReals
        )

        dispatch.balance = pyo.ConstraintList()
        for bus in case.bus:
            bus_id = bus.bus_i
            dispatch.balance.add(
                sum(dispatch.x[g] for g in generators_at_bus[bus_id])
                - sum(dispatch.f[l] for l in lines_from_bus[bus_id])
                + sum(dispatch.f[l] for l in lines_to_bus[bus_id])
                == bus.Pd
            )

        dispatch.flow_definition = pyo.ConstraintList()
        dispatch.angle_slack_definition = pyo.ConstraintList()
        dispatch.flow_slack_definition = pyo.ConstraintList()
        for l, branch in enumerate(case.branch):
            if not branch.status:
                dispatch.flow_definition.add(dispatch.f[l] == 0)
                continue

            angle_difference = (
                dispatch.theta[branch.fbus] - dispatch.theta[branch.tbus]
            )
            tap = branch.ratio if branch.ratio else 1.0
            susceptance = case.baseMVA / (branch.x * tap)
            dispatch.flow_definition.add(
                dispatch.f[l]
                == susceptance
                * (angle_difference - math.radians(branch.angle))
            )
            dispatch.angle_slack_definition.add(
                dispatch.angle_lower_slack[l]
                == angle_difference - math.radians(branch.angmin)
            )
            dispatch.angle_slack_definition.add(
                dispatch.angle_upper_slack[l]
                == math.radians(branch.angmax) - angle_difference
            )
            if branch.rateA > 0:
                dispatch.flow_slack_definition.add(
                    dispatch.flow_lower_slack[l]
                    == dispatch.f[l] + branch.rateA
                )
                dispatch.flow_slack_definition.add(
                    dispatch.flow_upper_slack[l]
                    == branch.rateA - dispatch.f[l]
                )

        dispatch.capacity_slack_definition = pyo.ConstraintList()
        for g in active_generators:
            dispatch.capacity_slack_definition.add(
                dispatch.capacity_lower_slack[g] == dispatch.x[g]
            )
            dispatch.capacity_slack_definition.add(
                dispatch.capacity_upper_slack[g]
                == case.gen[g].Pmax - dispatch.x[g]
            )

        def bid_coefficients(g):
            if scenario > 0 and g == scenario - 1:
                return (
                    model.w * a_true[g][0],
                    model.w * a_true[g][1],
                )
            return model.bid_a[g], model.bid_b[g]

        def generation_stationarity_rule(dispatch, g):
            bus_id = case.gen[g].bus
            bid_a, bid_b = bid_coefficients(g)
            return (
                2 * bid_a * dispatch.x[g]
                + bid_b
                - dispatch.lmp[bus_id]
                - dispatch.capacity_lower_dual[g]
                + dispatch.capacity_upper_dual[g]
                == 0
            )

        dispatch.generation_stationarity = pyo.Constraint(
            model.G, rule=generation_stationarity_rule
        )

        def flow_stationarity_rule(dispatch, l):
            branch = case.branch[l]
            lower_dual = (
                dispatch.flow_lower_dual[l]
                if l in model.limited_lines
                else 0
            )
            upper_dual = (
                dispatch.flow_upper_dual[l]
                if l in model.limited_lines
                else 0
            )
            return (
                dispatch.lmp[branch.fbus]
                - dispatch.lmp[branch.tbus]
                + dispatch.flow_dual[l]
                - lower_dual
                + upper_dual
                == 0
            )

        dispatch.flow_stationarity = pyo.Constraint(
            model.lines, rule=flow_stationarity_rule
        )

        def angle_stationarity_rule(dispatch, bus_id):
            terms = []
            for l in model.active_lines:
                branch = case.branch[l]
                tap = branch.ratio if branch.ratio else 1.0
                angle_terms = (
                    case.baseMVA / (branch.x * tap) * dispatch.flow_dual[l]
                    + dispatch.angle_lower_dual[l]
                    - dispatch.angle_upper_dual[l]
                )
                if branch.fbus == bus_id:
                    terms.append(-angle_terms)
                if branch.tbus == bus_id:
                    terms.append(angle_terms)
            return sum(terms) == 0 if terms else pyo.Constraint.Feasible

        dispatch.angle_stationarity = pyo.Constraint(
            model.buses, rule=angle_stationarity_rule
        )

        dispatch.capacity_lower_complementarity = pyo.SOSConstraint(
            model.G,
            rule=lambda block, g: [
                block.capacity_lower_dual[g],
                block.capacity_lower_slack[g],
            ],
            sos=1,
        )
        dispatch.capacity_upper_complementarity = pyo.SOSConstraint(
            model.G,
            rule=lambda block, g: [
                block.capacity_upper_dual[g],
                block.capacity_upper_slack[g],
            ],
            sos=1,
        )
        dispatch.angle_lower_complementarity = pyo.SOSConstraint(
            model.active_lines,
            rule=lambda block, l: [
                block.angle_lower_dual[l],
                block.angle_lower_slack[l],
            ],
            sos=1,
        )
        dispatch.angle_upper_complementarity = pyo.SOSConstraint(
            model.active_lines,
            rule=lambda block, l: [
                block.angle_upper_dual[l],
                block.angle_upper_slack[l],
            ],
            sos=1,
        )
        dispatch.flow_lower_complementarity = pyo.SOSConstraint(
            model.limited_lines,
            rule=lambda block, l: [
                block.flow_lower_dual[l],
                block.flow_lower_slack[l],
            ],
            sos=1,
        )
        dispatch.flow_upper_complementarity = pyo.SOSConstraint(
            model.limited_lines,
            rule=lambda block, l: [
                block.flow_upper_dual[l],
                block.flow_upper_slack[l],
            ],
            sos=1,
        )

    def output(dispatch, g):
        return dispatch.x[g] if g in model.G else 0

    def true_cost(dispatch, g):
        generation = output(dispatch, g)
        gencost = case.gencost[g]
        return sum(
            gencost.params[n] * generation ** (gencost.n - n - 1)
            for n in range(len(gencost.params))
        )

    base_dispatch = model.dispatch[0]
    base_social_cost = sum(
        true_cost(base_dispatch, g) for g in model.generators
    )
    deviation_cost_changes = []
    for g in model.generators:
        deviation_dispatch = model.dispatch[g + 1]
        bus_id = case.gen[g].bus
        base_output = output(base_dispatch, g)
        deviation_output = output(deviation_dispatch, g)
        base_loss = (
            true_cost(base_dispatch, g)
            - base_output * base_dispatch.lmp[bus_id]
        )
        deviation_loss = (
            true_cost(deviation_dispatch, g)
            - deviation_output * deviation_dispatch.lmp[bus_id]
        )
        deviation_cost_changes.append(deviation_loss - base_loss)

    model.true_social_cost = pyo.Param(initialize=C(a_true))
    model.val = pyo.Expression(
        expr=base_social_cost
        + model.v * sum(deviation_cost_changes)
        - model.p * model.true_social_cost
    )
    model.objective = pyo.Objective(expr=model.val, sense=pyo.maximize)
    return model


def separation_oracle(model, p, v, w, epsilon):
    model.p = p
    model.v = v
    model.w = w

    model = runModel(model, BestObjStop=epsilon)
    val = pyo.value(model.val)
    bid_a = [
        pyo.value(model.bid_a[i])
        if i in model.G
        else pyo.value(model.inactive_bid_a)
        for i in model.generators
    ]
    bid_b = [
        pyo.value(model.bid_b[i])
        if i in model.G
        else pyo.value(model.inactive_bid_b)
        for i in model.generators
    ]
    new_action = tuple((bid_a[i], bid_b[i]) for i in model.generators)
    return new_action, val
