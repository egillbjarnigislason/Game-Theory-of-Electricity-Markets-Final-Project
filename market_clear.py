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
    m.obj = pyo.Objective(expr=sum(joint_action[g][0] * m.x[g] ** 2 + joint_action[g][1] * m.x[g] for g in m.G), sense=pyo.minimize)
    
    # run model and get the optimal solution
    m = runModel(m)

    # remove the objective function from the model to prepare for the next iteration
    m.del_component(m.obj)


    return m


def get_costs(case, cleared_market):
    costs = []
    for g, gencost in enumerate(case.gencost):
        output = pyo.value(cleared_market.x[g]) if g in cleared_market.G else 0
        costs.append(pyo.value(sum(gencost.params[n] * output ** (gencost.n - n - 1) for n in range(len(gencost.params)))))
    return costs


def get_social_cost(case, cleared_market):
    social_cost = sum(get_costs(case, cleared_market))
    return social_cost

def get_prices(case, cleared_market):
    bus_to_demand_index = {bus.bus_i: i for i, bus in enumerate(case.bus, start=1)}
    prices = {}
    for bus in case.bus:
        constraint_index = bus_to_demand_index[bus.bus_i]
        constraint = cleared_market.demand[constraint_index]
        prices[bus.bus_i] = pyo.value(cleared_market.dual[constraint])
    return prices


def get_revenues(case, cleared_market):
    prices = get_prices(case, cleared_market)
    revenues = []
    for g, generator in enumerate(case.gen):
        output = pyo.value(cleared_market.x[g]) if g in cleared_market.G else 0
        revenues.append(output * prices[generator.bus])
    return revenues


def get_losses(case, cleared_market):
    costs = get_costs(case, cleared_market)
    revenues = get_revenues(case, cleared_market)
    losses = [costs[g] - revenues[g] for g in range(len(case.gen))]
    return losses
