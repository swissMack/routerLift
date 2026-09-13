# routerLift wiring map — Rev H

Every connection in the split design: stock FluidNC on a classic ESP32 moves the lift, and an
ESP32-S3 touch panel drives it over UART. Pin numbers come from `firmware/config.yaml` (verified on
the bench, 2026-09-13) and `hmi/include/pins.h`. **If this page and those files disagree, the files
win.**

Node colours: red = mains 230 V · orange = 24–36 V DC · yellow = +5 V · blue = 3.3 V logic ·
dashed = reserved or not yet fitted.

## Before power-up

| # | Check |
| --- | --- |
| 1 | **PSU 24–36 V only.** A 48 V supply destroys the TB6600 (abs max ≈40–42 V) |
| 2 | **TB6600 PUL+ DIR+ ENA+ to 3.3 V, not 5 V.** At 5 V the input opto never turns fully off, so steps go missing without any error |
| 3 | **Inductive sensors NPN only.** `LJ12A3-4-Z/BY` is right; any `/A…` suffix is PNP and puts 24 V on the GPIO |

## 1 · Power and system overview

One PSU feeds everything low-voltage. The E-stop sits in the mains supply, ahead of both
controllers, so neither can override it. Join every 0 V at a single star point next to the PSU.

```mermaid
flowchart LR
  classDef mains fill:#F6D5D1,stroke:#B3261E,color:#3A0B07
  classDef v24 fill:#F9E0C4,stroke:#C25E00,color:#3D1E00
  classDef v5 fill:#F5EBC2,stroke:#8C7000,color:#2F2500
  classDef v33 fill:#D6E6F2,stroke:#2C5F8A,color:#0E2436
  classDef board fill:#DDE4DF,stroke:#39433F,color:#15201B,stroke-width:2px

  subgraph MAINS["Mains 230 V"]
    INLET["Inlet L / N / PE<br/>via RCD"] --> FUSE["Fuse"] --> ESTOP["E-STOP mushroom<br/>NC, latching"]
  end
  ESTOP -->|"L, N"| PSU["PSU 24–36 V DC<br/>NOT 48 V"]
  ESTOP -->|"L"| CONT["Contactor<br/>see diagram 5"]
  CONT --> SOCKET["Router socket"]

  PSU -->|"24–36 V"| TB["TB6600 driver"]
  PSU -->|"24–36 V"| BUCK["Buck converter<br/>5 V, 2 A or more"]
  PSU -.->|"24 V"| IND["Inductive NPN<br/>limit sensors, if used"]

  BUCK -->|"5 V to VIN"| ESP["Motion ESP32<br/>FluidNC"]
  BUCK -->|"5 V"| HMI["ESP32-S3 panel<br/>4.3 in touch"]
  BUCK -->|"5 V"| RELAY["5 V relay module"]
  BUCK -->|"5 V"| MPG["MPG handwheel"]

  ESP -->|"3V3 pin"| COMMON["TB6600 PUL+ DIR+ ENA+<br/>input pull-ups"]
  ESP ---|"UART  TX17 to RX16"| HMI
  ESP -->|"GPIO 4"| RELAY
  RELAY -->|"coil"| CONT
  TB -->|"4-core shielded"| MOTOR["NEMA 23<br/>57HS76"]
  GND(("Star ground<br/>at the PSU"))

  class INLET,FUSE,ESTOP,CONT,SOCKET mains
  class PSU,TB,IND v24
  class BUCK,RELAY,MPG v5
  class COMMON v33
  class ESP,HMI,MOTOR,GND board
```

## 2 · Motion controller ESP32 — every pin

Everything that starts motion or protects the machine lands here, so it keeps working when the
panel has crashed or the UART link has dropped.

```mermaid
flowchart LR
  classDef board fill:#DDE4DF,stroke:#39433F,color:#15201B,stroke-width:2px
  classDef v33 fill:#D6E6F2,stroke:#2C5F8A,color:#0E2436
  classDef field fill:#FFFFFF,stroke:#6B7570,color:#1C2321
  classDef reserved fill:#FFFFFF,stroke:#9AA39E,color:#5A6661,stroke-dasharray:4 3

  subgraph INPUTS["Inputs"]
    HOME["Bottom switch<br/>HOME and neg limit, NC"]
    TOP["Top switch<br/>pos limit, NC"]
    PROBE["Touch-off plate"]
    FOOT["Foot switch, NO"]
    STOP["STOP button, NO<br/>flush, feed hold"]
    DRV["Driver ALARM<br/>future closed-loop"]
  end

  COND["Conditioning<br/>one channel each<br/>diagram 4"]

  HOME --> COND
  TOP --> COND
  PROBE --> COND
  FOOT --> COND
  DRV -.-> COND

  COND -->|"GPIO 33"| ESP
  COND -->|"GPIO 25"| ESP
  COND -->|"GPIO 32"| ESP
  COND -->|"GPIO 13"| ESP
  COND -.->|"GPIO 35"| ESP
  STOP -->|"GPIO 21 direct, to GND"| ESP

  ESP["ESP32 DevKit WROOM-32<br/>stock FluidNC v4.1.0"]

  subgraph OUTPUTS["Outputs"]
    PUL["TB6600 PUL−"]
    DIR["TB6600 DIR−"]
    ENA["TB6600 ENA−"]
    RIN["Relay module IN"]
    RX["Panel GPIO 17 RX"]
  end
  TX["Panel GPIO 18 TX"]

  ESP -->|"GPIO 26 STEP"| PUL
  ESP -->|"GPIO 27 DIR"| DIR
  ESP -->|"GPIO 14 ENABLE"| ENA
  ESP -->|"GPIO 4 router"| RIN
  ESP -->|"GPIO 17 TX"| RX
  TX -->|"GPIO 16 RX"| ESP
  RES34["GPIO 34<br/>held for feedback"] -.- ESP

  class ESP board
  class COND,PUL,DIR,ENA,RIN,RX,TX v33
  class HOME,TOP,PROBE,FOOT,STOP field
  class DRV,RES34 reserved
```

| GPIO | Signal | Goes to | FluidNC key |
| --- | --- | --- | --- |
| 26 | STEP | TB6600 PUL− | `step_pin` |
| 27 | DIR | TB6600 DIR− | `direction_pin` |
| 14 | ENABLE | TB6600 ENA− | `disable_pin` |
| 4 | Router on/off | Relay module IN | `Relay: output_pin` |
| 33 | Bottom limit, homes here | Conditioner ← switch | `limit_neg_pin` |
| 25 | Top limit | Conditioner ← switch | `limit_pos_pin` |
| 32 | Probe plate | Conditioner ← plate; croc clip on bit to GND | `probe: pin` (active low) |
| 13 | Foot switch | Conditioner ← switch to GND | `macro0_pin` (active low) |
| 21 | STOP (feed hold) | Button to GND, internal pull-up | `feed_hold_pin` (active low) |
| 17 | UART TX | Panel GPIO 17 (RX) | `uart1: txd_pin` |
| 16 | UART RX | Panel GPIO 18 (TX) | `uart1: rxd_pin` |
| 35 | Driver alarm, reserved | Conditioner, wired NC | not configured yet |
| 34 | Reserved | nothing; held for feedback hardware | — |
| 3V3 | 3.3 V out | TB6600 PUL+ DIR+ ENA+, conditioner pull-ups | — |
| VIN · GND | Power in | Buck 5 V · star ground | — |

## 3 · TB6600 driver and motor

Common-anode wiring: the + terminals share 3.3 V and the ESP32 pulls each − terminal low to switch
it. DIP switches: 1/8 microstep (1600 pulses/rev), **1.0–1.4 A per phase**.

```mermaid
flowchart LR
  classDef v33 fill:#D6E6F2,stroke:#2C5F8A,color:#0E2436
  classDef v24 fill:#F9E0C4,stroke:#C25E00,color:#3D1E00
  classDef board fill:#DDE4DF,stroke:#39433F,color:#15201B,stroke-width:2px
  classDef coil fill:#FFFFFF,stroke:#39433F,color:#15201B

  V33["ESP32 3V3 pin"]
  G26["ESP32 GPIO 26"]
  G27["ESP32 GPIO 27"]
  G14["ESP32 GPIO 14"]
  PSUP["PSU +24–36 V"]
  PSUN["PSU 0 V"]

  subgraph TB6600["TB6600 · 1/8 step · 1.0–1.4 A"]
    PULP["PUL+"]
    PULM["PUL−"]
    DIRP["DIR+"]
    DIRM["DIR−"]
    ENAP["ENA+"]
    ENAM["ENA−"]
    VCC["VCC"]
    GNDT["GND"]
    AP["A+"]
    AM["A−"]
    BP["B+"]
    BM["B−"]
  end

  V33 --> PULP
  V33 --> DIRP
  V33 --> ENAP
  G26 --> PULM
  G27 --> DIRM
  G14 --> ENAM
  PSUP --> VCC
  PSUN --> GNDT

  AP -->|"RED"| MOTOR
  AM -->|"GRN"| MOTOR
  BP -->|"YEL"| MOTOR
  BM -->|"BLU"| MOTOR
  MOTOR["NEMA 23 57HS76-3004A08<br/>shielded 4-core, away from sensor runs"]

  class V33,G26,G27,G14,PULP,PULM,DIRP,DIRM,ENAP,ENAM v33
  class PSUP,PSUN,VCC,GNDT v24
  class AP,AM,BP,BM coil
  class MOTOR board
```

> ⚠️ **Why 1.0–1.4 A, not the motor's 3.0 A.** The lift needs about 0.15 N·m and this motor makes
> about 2 N·m. There is no stall detection, so at full current a bad move drives the lift into its
> hard stop with more than ten times the force it needs.

## 4 · Input conditioning — one channel

Build five identical channels: HOME (33), TOP (25), PROBE (32), FOOT (13) and DRIVER ALARM (35).
The same channel takes a mechanical switch or an NPN inductive sensor with no config change.

```mermaid
flowchart LR
  classDef v33 fill:#D6E6F2,stroke:#2C5F8A,color:#0E2436
  classDef v24 fill:#F9E0C4,stroke:#C25E00,color:#3D1E00
  classDef part fill:#FFFFFF,stroke:#39433F,color:#15201B
  classDef board fill:#DDE4DF,stroke:#39433F,color:#15201B,stroke-width:2px

  subgraph MECH["Option A · mechanical roller switch"]
    MCOM["COM terminal"] --> MG["GND"]
    MNC["NC terminal"]
  end
  subgraph NPN["Option B · inductive NPN NC"]
    BRN["Brown"] --> P24["+24 V"]
    BLU["Blue"] --> P0["0 V"]
    BLK["Black = signal"]
  end

  MNC --> WIRE
  BLK -.-> WIRE
  WIRE["Signal wire<br/>shielded pair, shield to GND<br/>at controller end only"]

  V33["+3.3 V"] --> RPU["4.7 kΩ pull-up"]
  RPU --> WIRE
  WIRE --> RS["10 kΩ series"]
  RS --> NODE(("input node"))
  NODE --> CLAMP["BAT54S<br/>clamps to 3V3 and GND"]
  NODE --> CAP["100 nF to GND<br/>about 1 ms filter"]
  NODE --> GPIO["ESP32 GPIO"]

  class V33,GPIO v33
  class P24 v24
  class RPU,RS,CLAMP,CAP,MCOM,MNC,MG,BRN,BLU,BLK,P0 part
  class NODE board
```

**Reading it:** in normal use the NC contact or NPN output holds the wire at 0 V, so the GPIO reads
LOW. At the limit, or if a wire breaks, the pull-up takes it HIGH and FluidNC stops. That is why the
bare board alarmed until GPIO 33 and 25 were jumpered to GND.

**Probe and foot switch** use the same channel but are normally open: plate or pedal to the signal
wire, other side to GND. Their FluidNC pins are set `:low`, so pressing reads as active.

> ⚠️ **Pull-up placement is a drawing decision, not yet in the BOM.** The 4.7 kΩ pull-up sits on
> the sensor side of the 10 kΩ series resistor. On the GPIO side, a closed switch would only pull
> the input to about 2.2 V (a 10 k / 4.7 k divider), which may not read as LOW. Confirm on the bench.

## 5 · Mains and router switching

Three things must all agree before the router runs: the E-stop is out, the bit-change key is in,
and FluidNC has set GPIO 4 with `M3`. Only the last one is software.

```mermaid
flowchart LR
  classDef mains fill:#F6D5D1,stroke:#B3261E,color:#3A0B07
  classDef v5 fill:#F5EBC2,stroke:#8C7000,color:#2F2500
  classDef v33 fill:#D6E6F2,stroke:#2C5F8A,color:#0E2436
  classDef pe fill:#DFF0DA,stroke:#3C7A2E,color:#12300A

  L["Mains L"] --> F["Fuse"] --> E["E-STOP<br/>NC, latching"]
  E --> K["Contactor main contact<br/>L1 to T1"]
  K --> SL["Router socket L"]
  SNUB["RC snubber<br/>across the contact"] --- K

  E --> KEY["Bit-change KEY switch<br/>in series with coil"]
  KEY --> RC["Relay module contact<br/>COM to NO"]
  RC --> A1["Contactor coil A1"]
  A2["Contactor coil A2"] --> N["Mains N"]
  N --> SN["Router socket N"]

  G4["ESP32 GPIO 4"] --> RIN["Relay module IN"]
  B5["Buck 5 V"] --> RVCC["Relay module VCC"]
  G0["Star ground"] --> RGND["Relay module GND"]

  PE["Mains PE"] --> PE1["Enclosure"]
  PE --> PE2["Lift frame"]
  PE --> PE3["Router socket PE"]

  class L,F,E,K,SL,SNUB,KEY,RC,A1,A2,N,SN mains
  class B5,RVCC,RGND,G0 v5
  class G4,RIN v33
  class PE,PE1,PE2,PE3 pe
```

> ⚠️ **Check against your parts.** This drawing assumes a **230 V AC contactor coil**. For a 24 V
> coil, feed the key switch and relay contact from the 24 V rail instead of mains L, and return A2
> to 0 V. Size the contactor at twice the router's nameplate current or more. Mains cable and
> connectors must be a different type from every low-voltage run, so they cannot be cross-plugged.

## 6 · Operator panel

The panel holds everything that depends on job state: presets, zero validity, cycles. Five buttons
and the selector go through an MCP23017 on the touch controller's I²C bus, so they cost no GPIOs.

```mermaid
flowchart LR
  classDef board fill:#DDE4DF,stroke:#39433F,color:#15201B,stroke-width:2px
  classDef v33 fill:#D6E6F2,stroke:#2C5F8A,color:#0E2436
  classDef v5 fill:#F5EBC2,stroke:#8C7000,color:#2F2500
  classDef field fill:#FFFFFF,stroke:#6B7570,color:#1C2321
  classDef warn fill:#FFE9A8,stroke:#B37400,color:#3A2600

  MPG["MPG ZS80<br/>100 PPR, 5 V"] -->|"A, B at 5 V"| LS["Level shifter<br/>see warning below"]
  B5["Buck 5 V"] --> MPG
  LS -->|"A to GPIO 11"| S3
  LS -->|"B to GPIO 12"| S3

  S3["ESP32-S3 panel<br/>ESP32-4827S043"]
  S3 -->|"SCL 20, SDA 19"| BUS["I²C bus"]
  BUS --> GT["GT911 touch<br/>0x5D, on board"]
  BUS --> MCP["MCP23017<br/>address 0x20"]

  A0["A0 CYCLE START"] --> MCP
  A1["A1 ROUTER"] --> MCP
  A2["A2 BIT CHANGE"] --> MCP
  A3["A3 ZERO"] --> MCP
  A4["A4 PRESET"] --> MCP
  A5["A5 rough / fine toggle"] --> MCP
  A6["A6 foot switch mirror<br/>release edge"] -.-> MCP
  MCP -->|"B0"| LED["ROUTER LED<br/>with series resistor"]

  S3 -->|"GPIO 18 TX"| FRX["Motion ESP32 GPIO 16"]
  FTX["Motion ESP32 GPIO 17"] -->|"GPIO 17 RX"| S3
  STOP["STOP button"] -.->|"wires to motion GPIO 21,<br/>not to this board"| FST["Motion ESP32"]

  class S3,GT,MCP board
  class BUS,FRX,FTX,FST v33
  class MPG,B5 v5
  class A0,A1,A2,A3,A4,A5,A6,LED,STOP field
  class LS warn
```

| Panel pin | Signal | Notes |
| --- | --- | --- |
| GPIO 18 | UART TX → motion GPIO 16 | 3.3 V both ends, no shifter. Also join GND |
| GPIO 17 | UART RX ← motion GPIO 17 | 115200 baud |
| GPIO 11 · 12 | MPG A · B | Must arrive at 3.3 V |
| GPIO 20 · 19 | I²C SCL · SDA | Shared with the on-board GT911 |
| MCP A0–A5 | Buttons and selector | Dry contact to GND, internal pull-ups |
| MCP A6 | Foot switch mirror | Plan still unverified — see `firmware/README.md` |
| MCP B0 | ROUTER LED | Lit = live, blinking = warming up |
| GPIO 10 · 13 | Spare | GPIO 0 is a boot strap: never a button |

> ⚠️ **Open design issue — MPG level shifter.** `docs/BOM.md` specifies a **74HCT14**. A 74HCT14
> needs a 5 V supply, and then its outputs swing to 5 V, which can damage the S3's inputs. Use a
> **74LVC14 powered from 3.3 V** instead: 5 V-tolerant inputs, same Schmitt hysteresis, and two
> stages per channel stay non-inverting. Not yet changed in the BOM.
