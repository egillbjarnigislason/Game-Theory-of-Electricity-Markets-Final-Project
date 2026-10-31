import pyomo.environ as pyo

def replace_action(a, i, w, a_i_true):
    # Replace the i-th action in the joint action a with new_value
    new_a = list(a)
    new_a[i] = tuple([w * x for x in a_i_true])
    return tuple(new_a)

def create_finite_LP(case, a_true, C, c, H_subset):
    # LP model:
    model = pyo.ConcreteModel()

    # parameters
    model.w = pyo.Param(initialize=1.0, mutable=True)
    model.generators = pyo.Set(initialize=range(len(case.gen)))

    # variables
    model.p = pyo.Var(domain=pyo.NonNegativeReals)
    model.v = pyo.Var(domain=pyo.NonNegativeReals)

    # objective
    model.objective = pyo.Objective(expr=model.p, sense=pyo.minimize)

    # primary constraint
    model.constraint_rules = pyo.ConstraintList()

    for a in H_subset:
        model.constraint_rules.add(C(a) + model.v * sum(c(replace_action(a,i,model.w, a_true[i]),i) - c(a, i) for i in model.generators) <= model.p * C(a_true))

    return model
    
def runModel(model, addprint = False):
    solver = pyo.SolverFactory("gurobi")
    if not solver.available():
        raise RuntimeError("Gurobi solver is not available in your environment.")
    results = solver.solve(model, tee=addprint)
    status = results.Solver()['Termination condition'].value
    assert status == 'optimal', f'error occurred, status: {status}.  Check model!'
    return model

def solve_finite_LP(model, new_w):
    model.w = new_w
    model = runModel(model)
    return pyo.value(model.p), pyo.value(model.v)


def add_action_to_LP(model, a, C, c, a_true):
    model.constraint_rules.add(C(a) + model.v * sum(c(replace_action(a,i,model.w, a_true[i]),i) - c(a, i) for i in model.generators) <= model.p * C(a_true))