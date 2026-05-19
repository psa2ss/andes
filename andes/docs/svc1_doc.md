# SVC1 模型补充说明文档

## 1. 模型概述

SVC1 是 ANDES 仿真框架中的静止无功补偿器（Static Var Compensator，SVC）动态模型。SVC 是一种重要的 FACTS（柔性交流输电系统）设备，通过晶闸管控制电抗器（TCR）和固定电容器组配合，动态调节接入点的无功功率，从而维持母线电压稳定。

本模型参考 IEEE Std 421.5-2016、PSS/E SVC 模型（CSVGN 系列）以及 WECC SVC 模型设计，适用于电力系统暂态稳定仿真。

---

## 2. 物理背景

### 2.1 SVC 工作原理

SVC 由以下主要部件组成：
- **晶闸管控制电抗器（TCR）**：通过调节晶闸管触发角 α，连续调节等效电抗值，从而改变吸收的无功功率
- **固定电容器组（FC）**：提供固定的容性无功支撑
- **控制电路**：测量母线电压，与参考值比较，通过 PI 调节器产生 TCR 触发角指令

SVC 的等效电纳 Bsvc 可以在 Bmin（感性，吸收无功）到 Bmax（容性，发出无功）之间连续调节。

```
         +-------------------+
         |   FC (固定电容)   |
         |       +----+      |
  Bus ---+-------| FC |------+
         |       +----+      |
         |                    |
         |   TCR (可控电抗)   |
         |   +------------+   |
         +---| TCR (α)   |---+
             +------------+
                    |
                控制单元
```

### 2.2 控制框图

```
    Vref     +     Kp+Ki/s     Bmax
      │     (PI)     │        /──
      │      │       ▼       /
      ┌▼┐    │   ┌─────┐  ┌─▼─┐    ┌────┐   Bsvc
  +──►│+│───+──►│ PI  │─►│Lim│───►│TCR │──────►
  │    └▲┘       └─────┘  └───┘    └────┘
  │     │                              │
  │     │    ┌──────┐                   │
  │     +───►│ -1   │                   │
  │          └──────┘                   │
  │                                    │
  │    ┌──────────┐                     │
  │    │ Vm = V / │                     │
  │    │ (1+s·TR) │◄───────────────────┘
  │    └──────────┘
  │
  │    ┌──────────┐
  +────│ 测量延迟  │
       │ 1+s·TR   │
       └──────────┘
```

---

## 3. 模型数学描述

### 3.1 电压测量环节

母线电压经过一阶测量滤波环节：

$$
T_R \frac{dV_m}{dt} = V_{bus} - V_m
$$

其中：
- $V_{bus}$：母线电压实际值（p.u.）
- $V_m$：测量得到的电压（p.u.）
- $T_R$：测量时间常数（s）

**初始化**：$V_m^{(0)} = V_{bus}$

---

### 3.2 电压误差

$$
V_{err} = V_{ref} - V_m
$$

其中 $V_{ref}$ 为电压参考值（p.u.）

---

### 3.3 PI 调节器

$$
\frac{d\xi}{dt} = K_i \cdot V_{err}
$$

$$
B_{cmd} = \xi + K_p \cdot V_{err}
$$

其中：
- $\xi$：积分器状态变量
- $K_p$：比例增益（p.u.）
- $K_i$：积分增益（p.u.）

**初始化**：

$$
\xi^{(0)} = B_0 - K_p \cdot (V_{ref} - V_{bus})
$$

$$
B_{cmd}^{(0)} = B_0
$$

---

### 3.4 电纳限幅

$$
B_{cmd,lim} =
\begin{cases}
B_{min}, & B_{cmd} < B_{min} \\
B_{cmd}, & B_{min} \leq B_{cmd} \leq B_{max} \\
B_{max}, & B_{cmd} > B_{max}
\end{cases}
$$

其中：
- $B_{max}$：最大电纳（容性，p.u.），通常为正
- $B_{min}$：最小电纳（感性，p.u.），通常为负

---

### 3.5 TCR 触发延迟

$$
T_B \frac{dB_{svc}}{dt} = B_{cmd,lim} - B_{svc}
$$

其中：
- $B_{svc}$：SVC 实际输出电纳（p.u.）
- $T_B$：TCR 触发延迟时间常数（s）

**初始化**：$B_{svc}^{(0)} = B_0$

---

### 3.6 无功功率注入

SVC 向母线注入的无功功率为：

$$
Q_{inj} = -B_{svc} \cdot V_{bus}^2
$$

> **符号说明**：按照 ANDES 母线方程约定，容性电纳（$B_{svc} > 0$）对应发出无功（$Q_{inj} < 0$ 加入母线无功功率平衡方程），与 Shunt 模型符号约定一致。

---

## 4. 参数说明

### 4.1 输入文件参数表

| 参数 | 名称 | 默认值 | 单位 | 说明 |
|------|------|--------|------|------|
| `bus` | 母线索引 | 必填 | — | SVC 接入的母线 ID |
| `Sn` | 额定容量 | 100.0 | MVA | SVC 额定容量 |
| `Vn` | 额定电压 | 110.0 | kV | 接入点额定电压 |
| `fn` | 额定频率 | 60.0 | Hz | 系统额定频率 |
| `Vref` | 电压参考值 | 1.0 | p.u. | 控制目标电压 |
| `Kp` | 比例增益 | 100.0 | p.u. | PI 调节器比例增益 |
| `Ki` | 积分增益 | 10.0 | p.u. | PI 调节器积分增益 |
| `TR` | 测量时间常数 | 0.02 | s | 电压测量滤波时间常数 |
| `TV` | 调节器延时 | 0.01 | s | 电压调节器滞后时间常数（预留） |
| `Bmax` | 最大电纳 | 1.0 | p.u. | 容性最大电纳（发出无功上限） |
| `Bmin` | 最小电纳 | -1.0 | p.u. | 感性最小电纳（吸收无功上限） |
| `TB` | TCR 时间常数 | 0.05 | s | 晶闸管触发延迟时间常数 |
| `Kd` | 阻尼增益 | 0.0 | p.u. | 阻尼环节增益（为 0 时禁用） |
| `Td` | 阻尼时间常数 | 0.1 | s | 阻尼 Washout 环节时间常数 |
| `B0` | 初始电纳 | 0.0 | p.u. | 潮流计算得到的初始电纳 |

### 4.2 内部变量

| 变量 | 名称 | 类型 | 说明 |
|------|------|------|------|
| `Lmeas_y` | 测量电压 $V_m$ | State | 滤波后的母线电压测量值 |
| `verr` | 电压误差 $V_{err}$ | Algeb | $V_{ref} - V_m$ |
| `PI_xi` | 积分器状态 $\xi$ | State | PI 积分项输出 |
| `PI_y` | PI 总输出 | Algeb | $\xi + K_p \cdot V_{err}$ |
| `Bcmd` | 电纳指令 | Algeb | PI 调节器输出 |
| `Bcmd_lim` | 限幅后电纳指令 | Algeb | 经 Bmin/Bmax 限幅后的指令 |
| `TCR_y` | SVC 实际电纳 $B_{svc}$ | State | 经 TCR 延迟后的实际输出电纳 |

---

## 5. 初始化流程

1. **电压测量初始化**：$V_m^{(0)} = V_{bus}$（来自潮流解）
2. **电压误差初始化**：$V_{err}^{(0)} = V_{ref} - V_{bus}$
3. **积分器初始化**：$\xi^{(0)} = B_0 - K_p \cdot (V_{ref} - V_{bus})$
4. **PI 输出初始化**：$B_{cmd}^{(0)} = \xi^{(0)} + K_p \cdot V_{err}^{(0)} = B_0$
5. **限幅输出初始化**：$B_{cmd,lim}^{(0)} = \text{clip}(B_0, B_{min}, B_{max})$
6. **TCR 输出初始化**：$B_{svc}^{(0)} = B_0$

---

## 6. 测试算例说明

测试算例 `svc_test_case.py` 包含：

### 6.1 系统拓扑

```
    GEN (Slack)         GEN (PV)
       Bus 1 ─────────── Bus 2
        │                  │
        │                  │
        │                  │
       Line 1-3           Line 2-3
        │                  │
        ▼                  ▼
       Bus 3 (Load + SVC1)
```

- **Bus 1**：Slack 母线，$V = 1.02$ p.u.
- **Bus 2**：PV 母线，发电机 $P = 1.6$ p.u.，$V = 1.01$ p.u.
- **Bus 3**：PQ 母线，负荷 $P = 2.0$ p.u.，$Q = 1.0$ p.u.，SVC1 安装于此

### 6.2 暂态测试场景

| 时间 | 事件 | 目的 |
|------|------|------|
| t = 0.0 s | 仿真启动 | 系统处于稳态，SVC 维持 Bus 3 电压在 1.0 p.u. |
| t = 1.0 s | 负荷 Q 从 1.0 增至 1.3 p.u. | 模拟无功负荷突增，电压有下降趋势 |
| t = 1.0 s | Bus 3 三相短路故障（持续 0.1 s） | 测试大扰动下 SVC 的动态响应 |

### 6.3 运行测试

```bash
# 生成测试算例
cd /root/.openclaw/workspace/andes/cases
python3 svc_test_case.py

# 运行潮流计算
andes svc_test_case.xlsx

# 运行暂态仿真
andes -r tds svc_test_case.xlsx

# 绘制 Bus 3 电压曲线
andes plot svc_test_case.xlsx --var v --bus 3

# 绘制 SVC 电纳响应
andes plot svc_test_case.xlsx --var TCR_y --xln SVC1
```

---

## 7. 模型验证要点

1. **稳态验证**：在 t = 0 时刻，检查 $B_{svc} = B_0$，电压 $V_{bus} \approx V_{ref}$
2. **阶跃响应**：在 t = 1.0 s 增加无功负荷后，SVC 应增大容性电纳（$B_{svc}$ 向正方向变化），支撑母线电压
3. **限幅验证**：强制 SVC 指令超过 Bmax 时，输出应被限制在 Bmax
4. **动态特性**：TCR 延迟环节应使 $B_{svc}$ 呈一阶惯性响应，时间常数约为 $T_B$

---

## 8. 扩展与改进方向

1. **详细阻尼环节**：当前 `Kd` 参数预留但未启用，可增加基于电压变化率的阻尼 Washout 环节
2. **电压调节器超前-滞后环节**：增加 $T_V$ 对应的超前-滞后环节，改善动态响应
3. **多波段 SVC 模型**：参考 PSS/E CSVGN2，增加多个控制波段
4. **TCR 细节建模**：增加触发角直接建模，考虑谐波影响
5. **FACTS 协调控制**：与发电机励磁器、调速器协调，提升系统稳定性

---

## 9. 参考文献

1. IEEE Std 421.5-2016, *IEEE Recommended Practice for Excitation System Models for Power System Stability Studies*, Section 11 (SVC).
2. PSS/E Model Library, *SVC Models (CSVGN1, CSVGN2)*, Siemens.
3. Kundur, P., *Power System Stability and Control*, McGraw-Hill, 1994, Chapter 14.
4. Hingorani, N.G., and Gyugyi, L., *Understanding FACTS: Concepts and Technology of Flexible AC Transmission Systems*, IEEE Press, 2000.
5. CUI, Hantao, *ANDES User Guide*, https://github.com/cuihantao/andes
