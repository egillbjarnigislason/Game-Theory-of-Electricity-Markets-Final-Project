import math


def golden_search(rho_of_omega, omega_left, omega_right, tol=1e-4, max_iter=200):

    
    g = (math.sqrt(5) - 1) / 2  # golden number

    # Two test points inside the range
    omega_1 = omega_right - g * (omega_right - omega_left)
    omega_2 = omega_left + g * (omega_right - omega_left)
    rho_1 = rho_of_omega(omega_1)
    rho_2 = rho_of_omega(omega_2)

    for _ in range(max_iter):
        if omega_right - omega_left < tol:
            break

        if rho_1 < rho_2:
            # Minimum is on the left: move the right end in
            omega_right = omega_2
            omega_2, rho_2 = omega_1, rho_1  # reuse old point
            omega_1 = omega_right - g * (omega_right - omega_left)
            rho_1 = rho_of_omega(omega_1)    # one new LP solve
        else:
            # Minimum is on the right: move the left end in
            omega_left = omega_1
            omega_1, rho_1 = omega_2, rho_2  # reuse old point
            omega_2 = omega_left + g * (omega_right - omega_left)
            rho_2 = rho_of_omega(omega_2)    # one new LP solve

    best_omega = (omega_left + omega_right) / 2
    return best_omega, rho_of_omega(best_omega)


