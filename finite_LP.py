import pyomo.environ as pyo

def replace_action(a, i, w, a_i_true):
    # Replace the i-th action in the joint action a with new_value
    new_a = list(a)
    new_a[i] = tuple([pyo.value(w) * x for x in a_i_true])
    return tuple(new_a)

def create_finite_LP(case, a_true, C, c, H_subset):
    # LP model:
    model = pyo.ConcreteModel()

    # parameters
    model.w = pyo.Param(initialize=1.0, mutable=True)
    players = [g for g, gen in enumerate(case.gen) if gen.Pmax > 0]
    model.generators = pyo.Set(initialize=players)

    # variables
    model.p = pyo.Var(domain=pyo.NonNegativeReals)
    model.v = pyo.Var(domain=pyo.NonNegativeReals)

    # objective
    model.objective = pyo.Objective(expr=model.p, sense=pyo.minimize)

    # primary constraint
    model.constraint_rules = pyo.ConstraintList()

    # remember what is needed to rebuild the constraints when omega changes
    model.c_func, model.a_true, model.C_true = c, a_true, C(a_true)
    model.H, model.base = [], {}

    for a in H_subset:
        add_action_to_LP(model, a, C, c, a_true)

    return model

def make_constraint(model, a, w):
    # C(a) + v * sum_i (loss of i after switching to w * true bid - loss of i now) <= p * C(a_true)
    C_a, losses_a = model.base[a]
    gap = sum(model.c_func(replace_action(a, i, w, model.a_true[i]), i) - losses_a[i] for i in model.generators)
    return C_a + model.v * gap <= model.p * model.C_true
    
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
    # the switching losses depend on omega, so rebuild every constraint for the new omega
    model.del_component(model.constraint_rules)
    model.constraint_rules = pyo.ConstraintList()
    for a in model.H:
        model.constraint_rules.add(make_constraint(model, a, new_w))
    model = runModel(model)
    return pyo.value(model.p), pyo.value(model.v)


def add_action_to_LP(model, a, C, c, a_true):
    # C(a) and the losses at a do not depend on omega, so compute them once and store them
    model.H.append(a)
    model.base[a] = (C(a), {i: c(a, i) for i in model.generators})
    model.constraint_rules.add(make_constraint(model, a, pyo.value(model.w)))
