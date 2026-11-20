import numpy as np
import itertools
import pyomo.environ as pyo
# Find the empirical CCE POA when the generators can bid in a discrete set of actions.  



def create_full_set_of_actions(case, num_steps, min_a, max_a, min_b, max_b):
    # Create a full set of actions for each generator
    a_possible = np.linspace(min_a, max_a, num_steps)
    b_possible = np.linspace(min_b, max_b, num_steps)

    # Create a list of all possible actions for each generator
    possible_actions_for_each_generator = [(a, b) for a in a_possible for b in b_possible]

    # one bid per GENERATOR (bid number g belongs to generator g); SYNC units (Pmax = 0) only get (min_a, min_b)
    options_per_generator = [possible_actions_for_each_generator if g.Pmax > 0 else [(min_a, min_b)] for g in case.gen]

    # Create the full set of joint actions by taking the Cartesian product of the possible actions for each generator
    full_set_of_joint_actions = list(itertools.product(*options_per_generator))

    return full_set_of_joint_actions


def replace_action(joint_action, player_position, new_action):
    replaced_action = list(joint_action)
    replaced_action[player_position] = new_action
    return tuple(replaced_action)


def create_discrete_cce_lp(case, actions, a_star, C, c):
    players = [g for g, generator in enumerate(case.gen) if generator.Pmax > 0]

    action_list = list(actions)
    individual_actions = sorted(
        {action for joint_action in action_list for action in joint_action}
    )
    social_cost = {}
    player_cost = {}
    for index, joint_action in enumerate(action_list):
        social_cost[index] = C(joint_action)
        player_cost[index] = {
            player: c(joint_action, player) for player in players
        }

    benchmark_cost = C(a_star)

    model = pyo.ConcreteModel()

    # Parameters
    model.profile_index = pyo.RangeSet(0, len(action_list) - 1)
    model.social_cost = pyo.Param(
        model.profile_index, initialize=social_cost
    )
    model.benchmark_cost = pyo.Param(initialize=benchmark_cost)
    model.action_list = action_list

    # Variables
    model.profile_probability = pyo.Var(
        model.profile_index, domain=pyo.NonNegativeReals
    )

    # Objective
    model.objective = pyo.Objective(
        expr=sum(
            model.profile_probability[index]
            * model.social_cost[index]
            / model.benchmark_cost
            for index in model.profile_index
        ),
        sense=pyo.maximize,
    )

    # Constraints
    model.probability_sum = pyo.Constraint(
        expr=sum(
            model.profile_probability[index]
            for index in model.profile_index
        )
        == 1
    )
    model.cce_constraints = pyo.ConstraintList()
    for player_position, player in enumerate(players):
        for deviation in individual_actions:
            constraint_expr = 0
            for index, joint_action in enumerate(action_list):
                deviated_action = replace_action(
                    joint_action, player, deviation
                )
                constraint_expr += model.profile_probability[index] * (
                    player_cost[index][player]
                    - c(deviated_action, player)
                )
            model.cce_constraints.add(constraint_expr <= 0)

    

    # Solve the model
    solver = pyo.SolverFactory("gurobi")
    
    results = solver.solve(model)
    termination = results.solver.termination_condition
    if termination != pyo.TerminationCondition.optimal:
        raise RuntimeError(
            f"Discrete CCE LP failed with termination condition: {termination}."
        )
    return pyo.value(model.objective)

    


