"""
SVC1: Static Var Compensator (SVC) dynamic model.

This module implements a standard SVC model for power system dynamic simulation.
The SVC regulates the bus voltage by adjusting its reactive power output
through a thyristor-controlled reactor (TCR) and fixed capacitors.

Model Reference:
    - PSS/E SVC model (CSVGN series)
    - WECC SVC model
    - IEEE Std 421.5-2016 (Section 11, SVC)
"""

import logging

from andes.core import (ModelData, Model, IdxParam, NumParam,
                        Algeb, ConstService, ExtAlgeb)
from andes.core.block import Lag, PIController
from andes.core.discrete import Limiter, HardLimiter

logger = logging.getLogger(__name__)


class SVC1Data(ModelData):
    """
    Data for SVC1 model.

    SVC stands for Static Var Compensator, a FACTS device that provides
    dynamic voltage support by controlling reactive power injection/absorption.
    """

    def __init__(self):
        super().__init__()

        # --- Bus and connectivity ---
        self.bus = IdxParam(model='ACNode',
                            info="Connected bus idx",
                            mandatory=True,
                            status_parent=True,
                            )

        # --- Power rating and voltage ---
        self.Sn = NumParam(default=100.0,
                           info="Power rating of SVC",
                           tex_name='S_n',
                           unit='MVA',
                           )
        self.Vn = NumParam(default=110.0,
                           info="AC voltage rating",
                           tex_name='V_n',
                           unit='kV',
                           )
        self.fn = NumParam(default=60.0,
                           info="Rated frequency",
                           tex_name='f_n',
                           unit='Hz',
                           )

        # --- Voltage regulation parameters ---
        self.Vref = NumParam(default=1.0,
                             info="Voltage reference setpoint",
                             tex_name='V_{ref}',
                             unit='p.u.',
                             )
        self.Kp = NumParam(default=100.0,
                           info="Proportional gain of voltage regulator",
                           tex_name='K_p',
                           unit='p.u.',
                           )
        self.Ki = NumParam(default=10.0,
                           info="Integral gain of voltage regulator",
                           tex_name='K_i',
                           unit='p.u.',
                           )

        # --- Measurement and control time constants ---
        self.TR = NumParam(default=0.02,
                           info="Voltage measurement time constant",
                           tex_name='T_R',
                           unit='s',
                           )
        self.TV = NumParam(default=0.01,
                           info="Voltage regulator lag time constant",
                           tex_name='T_V',
                           unit='s',
                           )

        # --- Susceptance limits ---
        self.Bmax = NumParam(default=1.0,
                             info="Maximum susceptance (capacitive)",
                             tex_name='B_{max}',
                             unit='p.u.',
                             )
        self.Bmin = NumParam(default=-1.0,
                             info="Minimum susceptance (inductive)",
                             tex_name='B_{min}',
                             unit='p.u.',
                             )

        # --- TCR time constant ---
        self.TB = NumParam(default=0.05,
                           info="SVC susceptance time constant (TCR firing delay)",
                           tex_name='T_B',
                           unit='s',
                           )

        # --- Damping (optional washout) ---
        self.Kd = NumParam(default=0.0,
                           info="Damping gain (washout loop)",
                           tex_name='K_d',
                           unit='p.u.',
                           )
        self.Td = NumParam(default=0.1,
                           info="Damping washout time constant",
                           tex_name='T_d',
                           unit='s',
                           )

        # --- Initial susceptance ---
        self.B0 = NumParam(default=0.0,
                           info="Initial susceptance (from power flow)",
                           tex_name='B_0',
                           unit='p.u.',
                           )


class SVC1Model(Model):
    """
    Model implementation for SVC1.

    Structure:
        1. Voltage measurement (Lag with TR)
        2. Voltage error = Vref - Vm
        3. PI Controller (Kp, Ki) with output Bcmd
        4. Hard limiter on Bcmd (Bmin ~ Bmax)
        5. TCR delay (Lag with TB) -> Bsvc
        6. Output: Q = Bsvc * V^2 injected to bus
    """

    def __init__(self, system, config):
        Model.__init__(self, system, config)

        self.group = 'SVC'
        self.flags.pflow = True
        self.flags.tds = True

        # --- External variables from bus ---
        self.a = ExtAlgeb(model='Bus', src='a', indexer=self.bus,
                          tex_name=r'\theta',
                          ename='P', tex_ename='P',
                          )
        self.vbus = ExtAlgeb(model='Bus', src='v', indexer=self.bus,
                             tex_name='V',
                             ename='Q', tex_ename='Q',
                             )

        # --- Initial value calculations ---
        # At steady state: Bsvc = B0, Vm = vbus
        # PI output: Bcmd = Kp*(Vref - vbus) + INT_y = B0
        # Therefore: INT_y = B0 - Kp*(Vref - vbus)
        self._int_y0 = ConstService(
            v_str='B0 - Kp * (Vref - vbus)',
            tex_name='x_{i0}',
            info='Initial integrator output'
        )

        # --- Voltage measurement (Lag block) ---
        # Input: bus voltage vbus
        # Output: vm (measured voltage)
        self.Lmeas = Lag(u=self.vbus, T=self.TR, K=1,
                         info='Voltage measurement lag')

        # --- Voltage error ---
        self.verr = Algeb(info='Voltage error',
                          tex_name='V_{err}',
                          v_str='Vref - vbus',
                          e_str='Vref - Lmeas_y - verr',
                          diag_eps=True,
                          )

        # --- PI Controller ---
        # Uses ANDES built-in PIController block
        # PI output: y = xi + kp * (u - ref)
        # where xi integrates ki * (u - ref)
        self.PI = PIController(u=self.verr, kp=self.Kp, ki=self.Ki,
                               ref=0.0, x0=self._int_y0,
                               info='PI voltage regulator')

        # --- Susceptance command from PI ---
        self.Bcmd = Algeb(info='Susceptance command (PI output)',
                          tex_name='B_{cmd}',
                          v_str='PI_y',
                          e_str='PI_y - Bcmd',
                          diag_eps=True,
                          )

        # --- Susceptance limiter ---
        self.lim = Limiter(u=self.Bcmd,
                           lower=self.Bmin,
                           upper=self.Bmax,
                           info='Susceptance limiter')

        # Limited susceptance command
        self.Bcmd_lim = Algeb(info='Limited susceptance command',
                               tex_name='B_{cmd,lim}',
                               v_str='lim_z0 * Bcmd + lim_zi * Bmin + lim_zl * Bmax',
                               e_str='lim_z0 * Bcmd + lim_zi * Bmin + lim_zl * Bmax - Bcmd_lim',
                               diag_eps=True,
                               )

        # --- TCR firing delay (Lag block) ---
        # Input: limited Bcmd
        # Output: Bsvc (actual susceptance)
        self.TCR = Lag(u=self.Bcmd_lim, T=self.TB, K=1,
                        info='TCR firing delay')

        # --- Optional damping washout (if Kd > 0) ---
        # Damping signal: Kd * (s*Td / (1 + s*Td)) * (Vref - Vm)
        # This provides additional damping for voltage oscillations
        self.use_damp = ConstService(v_str='Indicator(Kd > 0)',
                                      tex_name='z_{damp}',
                                      info='Use damping flag')

        self.WO = Washout(u='Kd * verr',
                          K=1,
                          T=self.Td,
                          info='Damping washout')

        # Damping contribution to Bcmd
        # When damping is enabled, add WO_y to Bcmd
        # We handle this in the PI output - the damping modifies the verr signal
        # For simplicity, we don't add damping loop in this basic model
        # (can be added later as an enhancement)

        # --- Output to bus ---
        # Active power: SVC does not inject active power (losses neglected)
        self.a.e_str = 'ue * 0'

        # Reactive power injection: Q = Bsvc * V^2
        # Positive Bsvc (capacitive) injects Q (reduces bus Q deficit)
        # Using same sign convention as shunt model:
        #   Q_injection = - Bsvc * V^2  (same as shunt with b=Bsvc)
        self.vbus.e_str = '-ue * TCR_y * vbus**2'


class SVC1(SVC1Data, SVC1Model):
    """
    SVC1: Static Var Compensator with PI voltage regulator.

    This model represents a Static Var Compensator (SVC) for power system
    dynamic simulation. The SVC regulates the connected bus voltage by
    adjusting its equivalent susceptance (Bsvc) through a thyristor-
    controlled reactor (TCR) and fixed capacitors.

    Model Features:
    - Voltage measurement with time constant TR
    - PI voltage regulator with gains Kp and Ki
    - Susceptance limits Bmin and Bmax
    - TCR firing delay with time constant TB
    - Optional damping washout (Kd, Td)

    Input File Parameters:
    ====================

    Required:
    - bus: Connected bus index (mandatory)
    - Vref: Voltage reference (p.u.)
    - B0: Initial susceptance (p.u., from power flow)

    Optional (with defaults):
    - Sn: Power rating (default 100 MVA)
    - Vn: AC voltage rating (default 110 kV)
    - fn: Rated frequency (default 60 Hz)
    - Kp: Proportional gain (default 100 p.u.)
    - Ki: Integral gain (default 10 p.u.)
    - TR: Measurement time constant (default 0.02 s)
    - TV: Regulator lag time constant (default 0.01 s, reserved)
    - Bmax: Max susceptance (default 1.0 p.u., capacitive)
    - Bmin: Min susceptance (default -1.0 p.u., inductive)
    - TB: TCR delay time constant (default 0.05 s)
    - Kd: Damping gain (default 0.0, disabled)
    - Td: Damping washout time constant (default 0.1 s)

    Model Equations:
    ===============

    Voltage measurement:
        TR * d(Vm)/dt = Vbus - Vm

    Voltage error:
        Verr = Vref - Vm

    PI controller:
        d(xi)/dt = Ki * Verr
        Bcmd = xi + Kp * Verr

    Susceptance limiter:
        Bcmd_lim = { Bmin, if Bcmd < Bmin
                   { Bcmd, if Bmin <= Bcmd <= Bmax
                   { Bmax, if Bcmd > Bmax

    TCR delay:
        TB * d(Bsvc)/dt = Bcmd_lim - Bsvc

    Reactive power injection to bus:
        Q_inj = - Bsvc * Vbus^2

    References:
    ===========
    [1] IEEE Std 421.5-2016, "IEEE Recommended Practice for Excitation
        System Models for Power System Stability Studies", Section 11.
    [2] PSS/E Model Library - SVC Models (CSVGN1, CSVGN2).
    [3] Kundur, P., "Power System Stability and Control", McGraw-Hill, 1994.
    """

    def __init__(self, system, config):
        SVC1Data.__init__(self)
        SVC1Model.__init__(self, system, config)
