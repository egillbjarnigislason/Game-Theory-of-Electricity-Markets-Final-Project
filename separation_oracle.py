import pyomo.environ as pyo

import market_constraints as mc

def runModel(model, addprint = False, BestObjStop = None):
    solver = pyo.SolverFactory("gurobi")

    if BestObjStop is not None:
        solver.options['BestObjStop'] = BestObjStop

    if not solver.available():
        raise RuntimeError("Gurobi solver is not available in your environment.")
    results = solver.solve(model, tee=addprint)
    status = results.Solver()['Termination condition'].value
    assert status == 'optimal', f'error occurred, status: {status}.  Check model!'
    return model


def create_separation_oracle(case, min_a, max_a, min_b, max_b):
    
    # LP model:
    model = mc.build_constraints(case)


    # parameters
    model.p = pyo.Param(initialize=1.0, mutable=True)
    model.v = pyo.Param(initialize=1.0, mutable=True)
    model.w = pyo.Param(initialize=1.0, mutable=True)

    model.generators = pyo.Set(initialize=range(len(case.gen)))

    # variables
    model.val = pyo.Var(domain=pyo.Reals)
    model.bid_a = pyo.Var(model.generators, domain=pyo.NonNegativeReals, bounds=(min_a, max_a))
    model.bid_b = pyo.Var(model.generators, domain=pyo.NonNegativeReals, bounds=(min_b, max_b))


    # objective
    model.objective = pyo.Objective(expr=model.val, sense=pyo.maximize)

    # constraints
    def stationarity_constraint_rule(model, i):
        return 2 * model.bid_a[i] * model.x[i] + model.bid_b[i] - model.val == 0

    model.stationarity_constraints = pyo.Constraint(model.generators, rule=stationarity_constraint_rule)

    # TODO: Add KKT constraints    

        
    return model

def separation_oracle(model, p, v, w, epsilon):
    model.p = p
    model.v = v
    model.w = w
    
    model = runModel(model, BestObjStop = epsilon)

    val = pyo.value(model.val)
    bid_a = [pyo.value(model.bid_a[i]) for i in model.generators]
    bid_b = [pyo.value(model.bid_b[i]) for i in model.generators]

    new_a = tuple([(bid_a[i], bid_b[i]) for i in model.generators])

    return (new_a, val)