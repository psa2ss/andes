"""
SVC1 Test Case for ANDES Transient Dynamic Simulation (TDS)

This test case contains a simple 3-bus system with:
  - Bus 1: Slack bus (V=1.02 p.u.)
  - Bus 2: PV bus (Gen, P=1.6 p.u., V=1.01 p.u.)
  - Bus 3: PQ bus (Load, P=2.0 p.u., Q=1.0 p.u.)
  - Line 1-2: Z = 0.02 + j0.08 p.u.
  - Line 2-3: Z = 0.01 + j0.04 p.u.
  - Line 1-3: Z = 0.0125 + j0.05 p.u.
  - SVC at Bus 3: B0=0.1 p.u., Vref=1.0 p.u.

Test Scenario:
  - At t=1.0s, apply a 0.3 p.u. reactive load step at Bus 3
    (simulating voltage drop and SVC dynamic response)
  - Observe SVC injecting/absorbing reactive power to maintain voltage

To run:
    andes -r tds svc_test_case.xlsx
    andes plot svc_test_case.xlsx --var v --bus 3 --xln SVC
"""

from andes.io.xlsx import CaseLoader

# ============================================================
# Bus Data
# ============================================================
# Bus: idx, Vn, v0, a0, area, zone, vmax, vmin
bus_data = [
    [1, 110.0, 1.02, 0.0, 1, 1, 1.1, 0.9],  # Slack bus
    [2, 110.0, 1.01, 0.0, 1, 1, 1.1, 0.9],  # PV bus
    [3, 110.0, 1.0,  0.0, 1, 1, 1.1, 0.9],  # PQ bus (SVC location)
]

# ============================================================
# AC Line Data
# ============================================================
# Line: idx, from, to, r, x, b, status
line_data = [
    [1, 1, 2, 0.02, 0.08, 0.0, 1],
    [2, 2, 3, 0.01, 0.04, 0.0, 1],
    [3, 1, 3, 0.0125, 0.05, 0.0, 1],
]

# ============================================================
# Static Generator Data (for power flow initialization)
# ============================================================
# StaticGen: idx, bus, Sn, Vn, u, P, Q, Pmax, Pmin, Qmax, Qmin
static_gen_data = [
    [1, 1, 100.0, 110.0, 1, 0.0, 0.0, 100.0, 0.0, 100.0, -100.0],  # Slack
    [2, 2, 100.0, 110.0, 1, 1.6, 0.8, 100.0, 0.0, 100.0, -100.0],  # PV gen
]

# ============================================================
# Synchronous Generator Data (for dynamic simulation)
# ============================================================
# SynGen (GENROU): idx, bus, gen, Sn, Vn, fn, u, xd, xq, xd1, xd2, xq1, xq2,
#                      Td10, Td20, Tq10, Tq20, M, D, ra, xl, kp, kw
syngen_data = [
    [1, 1, 1, 100.0, 110.0, 60.0, 1, 1.9, 1.7, 0.302, 0.204, 1.7, 0.3,
     8.0, 0.04, 0.8, 0.02, 6.0, 0.0, 0.0, 0.0, 0.0],  # Slack gen (GENROU)
    [2, 2, 2, 100.0, 110.0, 60.0, 1, 1.9, 1.7, 0.302, 0.204, 1.7, 0.3,
     8.0, 0.04, 0.8, 0.02, 6.0, 0.0, 0.0, 0.0, 0.0],  # PV gen (GENROU)
]

# ============================================================
# Exciter Data (IEEET1 for each generator)
# ============================================================
# Exciter: idx, syn, TR, KA, TA, VRMAX, VRMIN, KE, TE, KF, TF, E1, SE1, E2, SE2, u
exciter_data = [
    [1, 1, 0.02, 5.0, 0.04, 7.3, -7.3, 1.0, 0.8, 0.1, 1.0, 0.0, 0.0, 1.0, 1.0, 1],
    [2, 2, 0.02, 5.0, 0.04, 7.3, -7.3, 1.0, 0.8, 0.1, 1.0, 0.0, 0.0, 1.0, 1.0, 1],
]

# ============================================================
# Governor Data (TGOV1 for each generator)
# ============================================================
# Gov (TGOV1): idx, syn, R, VMAX, VMIN, T1, T2, T3, Dt, u
governor_data = [
    [1, 1, 0.05, 1.2, 0.0, 0.1, 0.2, 10.0, 0.0, 1],
    [2, 2, 0.05, 1.2, 0.0, 0.1, 0.2, 10.0, 0.0, 1],
]

# ============================================================
# Static Load Data
# ============================================================
# PQ: idx, bus, Sn, Vn, u, P, Q
pq_data = [
    [1, 3, 100.0, 110.0, 1, 2.0, 1.0],  # Load at bus 3
]

# ============================================================
# SVC Data (SVC1 model)
# ============================================================
# SVC1: idx, bus, Sn, Vn, fn, Vref, Kp, Ki, TR, TV, Bmax, Bmin, TB, Kd, Td, B0, u
svc_data = [
    [1, 3, 100.0, 110.0, 60.0, 1.0, 100.0, 10.0, 0.02, 0.01, 1.0, -1.0, 0.05, 0.0, 0.1, 0.1, 1],
]

# ============================================================
# Fault Event (for transient simulation)
# ============================================================
# Fault: idx, bus, t, duration, R, X, u
fault_data = [
    [1, 3, 1.0, 0.1, 0.0, 0.0, 1],  # Temporary fault at bus 3 at t=1.0s
]

# ============================================================
# Toggle Event (for SVC dynamic test: increase load at bus 3)
# ============================================================
# Toggle: idx, model, dev, action, t, u
# We'll add a load step by toggling an additional load ON at t=1.0s
# Alternative: use Alter to modify load P and Q

# ============================================================
# Alter Event (modify load at bus 3 to test SVC response)
# ============================================================
# Alter: idx, model, dev, field, value, t, u
alter_data = [
    [1, 'PQ', 1, 'Q', 1.3, 1.0, 1],  # Increase Q at bus 3 from 1.0 to 1.3 at t=1.0s
]

# ============================================================
# Build Case and Save to Excel
# ============================================================
if __name__ == '__main__':
    case = CaseLoader()

    # Add data to case
    case.add_data('Bus', bus_data,
                  columns=['idx', 'Vn', 'v0', 'a0', 'area', 'zone', 'vmax', 'vmin'])

    case.add_data('Line', line_data,
                  columns=['idx', 'from', 'to', 'r', 'x', 'b', 'u'])

    case.add_data('StaticGen', static_gen_data,
                  columns=['idx', 'bus', 'Sn', 'Vn', 'u', 'P', 'Q', 'pmax', 'pmin', 'qmax', 'qmin'])

    case.add_data('GENROU', syngen_data,
                  columns=['idx', 'bus', 'gen', 'Sn', 'Vn', 'fn', 'u',
                           'xd', 'xq', 'xd1', 'xd2', 'xq1', 'xq2',
                           'Td10', 'Td20', 'Tq10', 'Tq20', 'M', 'D', 'ra', 'xl', 'kp', 'kw'])

    case.add_data('IEEET1', exciter_data,
                  columns=['idx', 'syn', 'TR', 'KA', 'TA', 'VRMAX', 'VRMIN',
                           'KE', 'TE', 'KF', 'TF', 'E1', 'SE1', 'E2', 'SE2', 'u'])

    case.add_data('TGOV1', governor_data,
                  columns=['idx', 'syn', 'R', 'VMAX', 'VMIN', 'T1', 'T2', 'T3', 'Dt', 'u'])

    case.add_data('PQ', pq_data,
                  columns=['idx', 'bus', 'Sn', 'Vn', 'u', 'P', 'Q'])

    case.add_data('SVC1', svc_data,
                  columns=['idx', 'bus', 'Sn', 'Vn', 'fn', 'Vref', 'Kp', 'Ki',
                           'TR', 'TV', 'Bmax', 'Bmin', 'TB', 'Kd', 'Td', 'B0', 'u'])

    case.add_data('Fault', fault_data,
                  columns=['idx', 'bus', 't', 'duration', 'R', 'X', 'u'])

    case.add_data('Alter', alter_data,
                  columns=['idx', 'model', 'dev', 'field', 'value', 't', 'u'])

    # Save to Excel file
    output_file = 'svc_test_case.xlsx'
    case.to_excel(output_file)
    print(f"Test case saved to {output_file}")
    print("To run transient simulation:")
    print(f"  andes -r tds {output_file}")
    print("To plot results:")
    print(f"  andes plot {output_file} --var v --bus 3")
    print(f"  andes plot {output_file} --var Bsvc_y --xln SVC1")
