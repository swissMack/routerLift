# Lift body alternatives — full-size router carriages

Shortlist compiled 2026-09-04, as a fallback to the sauter FML-P selected in
`MECHANICS-RevH.md`. All three take Ø 88.9 mm (3½") and Ø 107 mm (4.2") router
motors — Bosch 1617/1618, DeWalt 618, Porter-Cable 690/890/7518, Triton — with
reducing rings down to Ø 65 mm. The FML-P takes only a Ø 43 mm neck.

All three are JessEm Mast-R-Lift II derivatives: fixed lead screw driven by a
crank through the insert plate, carriage nut travels on two guide columns in
linear bearings. Prices are list prices seen on 2026-09-04 and move weekly.

## The shortlist

| # | Lift | Where | Price seen | Carriage | Travel | Lead | `steps_per_mm` at 1600 pulse/rev | Full-step | Plate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **ENJOYWOOD Heavy Duty Precision Router Lift** | Banggood `p-2043874` | US$289.99 | 65 / 69 / 80 / 88.9 / 107 mm variants | ~100 mm¹ | 1/16" = 1.5875 mm¹ | 1007.87 | 0.0079 mm | 298 × 235 × 10 mm¹ |
| 2 | **Wnew Heavy Duty Router Lift** | Banggood `p-1963502`; same item on AliExpress `2251832270838858` (JGC factory no. GC22072701) | not rendered on Banggood; US$519.99 at resellers | 107 mm + 65/69/80/88.9 rings | 100 mm | 1/16" = 1.5875 mm | 1007.87 | 0.0079 mm | 298 × 235 × 10 mm, ~10 kg |
| 3 | **SpeTool P01002** | AliExpress `1005010199458196` (CN) and `3256812598633138` (DE warehouse) | US$324.95 direct | 65–107 mm infinitely adjustable clamp | 107 mm | 20 TPI = 1.27 mm | 1259.84 | 0.00635 mm | 298 × 235 × 9.5 mm, ~9 kg, dust port |

¹ Banggood's page did not render specs. Figures are from the identical JGC-family
design (ZahyoX RL01 / Wnew) and must be confirmed on the listing before ordering.

Banggood ships the Wnew from a **CZ warehouse** as well as CN, and the SpeTool has a
**DE warehouse** listing — both matter for Swiss import handling.

## How they compare with the FML-P

| | sauter FML-P | These three |
| --- | --- | --- |
| Router | Ø 43 mm neck, ≤ 1,100 W spindle motor | Full-size Ø 88.9 / 107 mm routers |
| Travel | 65 mm — **fails MEC-01 (≥ 75 mm)** | 100–107 mm — **meets MEC-01** |
| Lead | 1.5 mm | 1.5875 or 1.27 mm — all beat MOT-01 |
| Drive from below | **Confirmed by Sauter**: hex socket on the screw's lower end, in a bearing block | **No — verified from the Wnew manual, see below.** The screw is cantilevered from a bearing base under the plate; its lower end is bare thread, unsupported, with no drive feature |
| Self-locking | Yes, ~2.3° lead angle | **Not relied on by the maker.** The Wnew has a PEEK-and-spring friction brake on the screw "to prevent the motor from sinking due to resonance" — i.e. it creeps under router vibration unless braked |
| Weight on the screw | ~8 kg carriage + spindle | Similar: ~5 kg carriage + 3–5 kg router. §5.1 torque figure still holds |
| Price | €329 B-stock / €378 | US$290–520 |

## What the Wnew manual shows (2026-09-04)

Manual at `reference/wnew-router-lift-manual-2021.pdf` (Wnew "Inverted Lifting System of
Engraving Machine", v1, 01/2021, Chinese + English). Read against the drive question:

| Figure | What it shows | Consequence |
| --- | --- | --- |
| 2-1 to 2-4, 3-6, 5-1 | The lead screw is held in a **screw base under the plate** and stands free from it. The carriage rides a **bronze nut** bolted on with three screws. Beyond the nut the screw is **bare thread to its end** | No lower hex, no lower bearing. Rev A's direct-coupled bracket **does not transfer** |
| 2-1 | The nut travels the full screw length; at full-down it sits at the free end | Anything fitted to the screw end **costs travel** — the nut cannot pass it |
| 3-11 / 3-12 | A grub screw in the screw base presses a **PEEK stick and spring** against the screw. "Tightening can prevent the motor from sinking due to resonance" | The screw is **not trusted to hold under vibration**. Either keep the brake set (adds friction torque the stepper must overcome — measure it) or hold with motor current. `idle_ms: 255` stays a necessity here, not a preference |
| 3-14, 3-16 | Crank engages a hex on the screw's top end through the plate. Sleeves supplied: 10 mm and 13 mm | Top hex is one of those two sizes — unverified which |
| p.14 | Stroke 100 mm, plate **300 × 235 × 10 mm**, body 290 mm tall | Plate is 300, not 298 as resellers list. Travel meets MEC-01 |
| p.14 | Lead not stated anywhere | 1.5875 mm is inferred from the family, still unmeasured |

**So the Wnew cannot be driven from below as it ships.** The two viable routes:

- **Belt drive from the side.** GT2/GT3 pulley clamped to the screw directly under the
  screw base, motor on a bracket beside the lift. Costs the pulley's width in travel —
  about 15–20 mm, leaving ~80 mm, which still meets MEC-01. Adds belt compliance to the
  MOT-02 backlash budget; use a tensioner. This is the workable option.
- **Machine the free end.** Turn a plain diameter and flat onto the screw end, add a
  support bearing to the motor bracket, couple directly. Loses the coupling length in
  travel and needs a lathe. Not recommended over the belt.

The ENJOYWOOD and SpeTool are the same architecture and should be assumed identical
until their manuals say otherwise.

## What changes in the design if one of these is chosen

1. **Drive interface is the open question, not the router fit.** Rev A's rigid bracket
   coupled straight to a lower hex assumes a bearing-supported screw end. The Wnew
   manual shows there is none, and the other two are the same design. The belt drive
   above becomes the plan.
2. `SCREW_LEAD_MM` becomes 1.5875 or 1.27 — imperial leads, so `steps_per_mm` is not a
   round number. The commissioning measurement in `firmware/README.md` stays the authority.
3. The 5.1 current-limit argument is unchanged: still ~0.15 N·m needed, still set the
   TB6600 to 1.0–1.4 A/phase. Add the friction brake's drag if it is kept set.
4. MEC-01 no longer needs revising down, but the belt pulley spends 15–20 mm of the
   100 mm, so the margin is ~5 mm, not 25.
5. MEC-02 (holds position unpowered) is **not** given by the mechanism. It comes from
   the friction brake or from motor holding current.

## Recommendation

If the requirement is genuinely a full-size router, take **#1 (ENJOYWOOD)** or **#2
(Wnew)** — same mechanism, choose on price and warehouse — and plan the belt drive. Take
**#3 (SpeTool)** if a DE warehouse or the finer 1.27 mm lead is worth the extra cost.

If the Ø 43 mm spindle-motor route is acceptable, the FML-P remains the better
engineering choice: the drive-from-below interface is manufacturer-confirmed, needs no
belt, and its screw is self-locking without a brake.

## Sources

- Banggood ENJOYWOOD heavy duty: https://usa.banggood.com/ENJOYWOOD-Heavy-Duty-Precision-Router-Lift-Router-Table-Lift-System-for-65mm-or-69mm-or-80mm-or-88_9mm-or-107mm-Diameter-Wood-Routers-p-2043874.html
- Banggood Wnew heavy duty: https://www.banggood.com/Wnew-Woodworking-Heavy-Duty-Router-Lift-with-Aluminium-Router-Table-Insert-Plate-Woodworking-Tools-p-1963502.html
- AliExpress Wnew/JGC item: https://www.aliexpress.com/item/2251832270838858.html
- JGC factory listing: https://www.jgctools.com/goods/detail/291
- ZahyoX RL01 spec sheet (same family): https://zahyox.com/products/rl01
- Wnew reseller spec + price: https://levoite.com/products/wnew-heavy-duty-router-lift-router-table-lift-system
- SpeTool P01002 spec sheet: https://spetools.com/products/router-lift-p01002
- SpeTool on AliExpress: https://www.aliexpress.us/item/3256812598633138.html and https://www.aliexpress.com/item/1005010199458196.html
