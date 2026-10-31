import pyomo.environ as pyo


def runModel(model, addprint = False):
    solver = pyo.SolverFactory("gurobi")
    if not solver.available():
        raise RuntimeError("Gurobi solver is not available in your environment.")
    results = solver.solve(model, tee=addprint)
    status = results.Solver()['Termination condition'].value
    assert status == 'optimal', f'error occurred, status: {status}.  Check model!'
    return model


def clear_market(case, m, joint_action):
    
    # Set the objective function to minimize the total generation cost
    m.obj = pyo.Objective(expr=sum(joint_action[g][0] * m.x[g] ** 2 + joint_action[g][1] * m.x[g] for g in range(len(case.gen))), sense=pyo.minimize)

    # run model and get the optimal solution
    m = runModel(m)

    # remove the objective function from the model to prepare for the next iteration
    m.del_component(m.obj)

    return m


def get_costs(case, cleared_market):
    costs = [pyo.value(sum(case.gencost[g].params[n] * cleared_market.x[g] ** (case.gencost[g].n - n) for n in range(len(case.gencost[g].params)))) for g in range(len(case.gencost))]
    return costs


def get_social_cost(case, cleared_market):
    social_cost = sum(get_costs(case, cleared_market))
    return social_cost

def get_losses(case, cleared_market, joint_action):
    costs = get_costs(case, cleared_market)
    revenues = [pyo.value(joint_action[g][0] * cleared_market.x[g] ** 2 + joint_action[g][1] * cleared_market.x[g]) for g in range(len(case.gen))]
    losses = [costs[g] - revenues[g] for g in range(len(case.gen))]
    return losses



    

