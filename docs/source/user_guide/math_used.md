# Appendix: Mathematics and Physics Used

{math}` `

## Weather models

### U and V grib components

Weather models provide the  $u_{10}$ and $v_{10}$ components of the wind at 10m on a grid (e.g., 0.25° for GFS and IFS) by time intervals $step_i$ (1h or 3h for GFS and IFS).

If we are looking for the wind speed at a point P and at a time T between $step_i$ and $step_{i+1}$:

- We calculate the values of $u_{10}$ and $v_{10}$ at point P by interpolation in space. We find the 4 grid points surrounding point P and perform a bilinear interpolation to obtain $u_{10}$ and $v_{10}$ at point P for each time values $step_i$ and $step_{i+1}$:

- The final values of $u_{10}$ and $v_{10}$ at point P at time T are calculated by a time interpolation of the values at $step_i$ and $step_{i+1}$:

### Wind at 10 m

The wind speed at 10m is calculated by
$$
tws_{10} = \sqrt{u_{10}^2 + v_{10}^2}
$$ 
And the true direction of ythe wind : 
$$
twd_{10} = \operatorname{atan2}(u_{10}, v_{10})
$$
## Ground Speed

###  Wall effect

The speed at 1.50m (which we will refer to as ground speed $tws$) obeys the wall effect
$$
tws = tws_{10} \cdot \frac{\ln\left(\frac{1.5}{{rug}}\right)}{\ln\left(\frac{10}{rug}\right)}
$$
where the value $rug$ is determined by the nature of the terrain.

### Roughness and terrain

The land cover used to find the nature of the terrain is the Global Wind Atlas v4 (landcover) file which comes from the European Space Agency's (ESA) WorldCover v200 dataset.

*Floors, R. et al. (2025) Global Wind Atlas v4 (orography), 10.11583/DTU.28955282*

## Wind along the trajectory 

If the wind speed and direction are given by $Tws$ (True Wind Speed) and $Twd$ (True Wind Direction)

$V_{windalong}$: wind speed along the trajectory
$bearing$: direction of the cyclist

We have the formula  :    
$$
V_{windalong} = Tws * cos(Twd- bearing)
$$

![](/_static/Windalong.png)

## Relative speed

The relative speed is given by: 
$$
V_{rel}=V_{bike} ​​+ V_{windalong}
$$
## Forces

### Drag Force

$$
F_D = 1/2 * {\rho} * {C_d} * {A} * V_{rel}^2
$$

$\rho$ is the air density,

$CD$ is the drag coefficient, and $A$ is the effective frontal area. $Cd$ and $A$ are combined into a single variable, often denoted $C_dA$.

### Rolling resistance 

$$
F_R= {C_{rr}} * {m} * {g}
$$
 ${C_{rr}}$ is the rolling resistance coefficient

### Gravity

$$
F_G=  {m} * {g} *  \operatorname{sin}(\theta)
$$
$\theta$ is the angle of the slope 

### Acceleration 

$$
F_A={m}*{a}
$$

### Power balance

Power output required from the cyclist :
$$
P_{cycliste}=({F_D}+{F_R}+{F_G}+{F_A})*V_{²}
$$

## Crosswind (yaw) & variation of CDA

![](/_static/Yaw.png)

The crosswind changes the angle of incidence (yaw : $\gamma$) of the cyclist-bike combination, and $C_dA$ becomes dependent on $\gamma$ :  $C_dA(\gamma)$. 

A common approximation is used :
$$
CdA_{eff} = CdA \times (1 + 0,02 \times \frac{|\gamma|}{10})
$$