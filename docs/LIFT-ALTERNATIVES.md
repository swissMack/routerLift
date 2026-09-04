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
| Drive from below | **Confirmed by Sauter**: hex socket on the screw's lower end, in a bearing block | **Unverified.** Top crank socket only. The screw's lower end is free inside the carriage — whether it protrudes and can be coupled is unknown |
| Self-locking | Yes, ~2.3° lead angle | Same order of lead angle on a ~12 mm screw — expect yes, measure per ACC-04 |
| Weight on the screw | ~8 kg carriage + spindle | Similar: ~5 kg carriage + 3–5 kg router. §5.1 torque figure still holds |
| Price | €329 B-stock / €378 | US$290–520 |

## What changes in the design if one of these is chosen

1. **Drive interface is the open question, not the router fit.** Rev A's rigid bracket
   coupled straight to a lower hex assumes a bearing-supported screw end. None of the
   three is known to have one. Two ways to close it, both need the lift in hand:
   - **Belt drive under the plate.** Pulley on the screw between the top plate and the
     carriage, motor beside the lift. This is how these clones are usually motorised.
     Adds a belt to the backlash budget (MOT-02) — use a GT2/GT3 with a tensioner.
   - **Direct coupling to the free screw end**, if it protrudes below the carriage at
     full-up. Needs a bottom support bearing added to the bracket, or the screw end
     whips.
2. `SCREW_LEAD_MM` becomes 1.5875 or 1.27 — imperial leads, so `steps_per_mm` is not a
   round number. The commissioning measurement in `firmware/README.md` stays the authority.
3. The 5.1 current-limit argument is unchanged: still ~0.15 N·m needed, still set the
   TB6600 to 1.0–1.4 A/phase.
4. MEC-01 no longer needs revising down.

## Recommendation

If the requirement is genuinely a full-size router, take **#1 (ENJOYWOOD)** or **#2
(Wnew)** — same mechanism, choose on price and warehouse — and plan the belt drive. Take
**#3 (SpeTool)** if a DE warehouse or the finer 1.27 mm lead is worth the extra cost.

If the Ø 43 mm spindle-motor route is acceptable, the FML-P remains the better
engineering choice: the drive-from-below interface is manufacturer-confirmed and needs
no belt.

## Sources

- Banggood ENJOYWOOD heavy duty: https://usa.banggood.com/ENJOYWOOD-Heavy-Duty-Precision-Router-Lift-Router-Table-Lift-System-for-65mm-or-69mm-or-80mm-or-88_9mm-or-107mm-Diameter-Wood-Routers-p-2043874.html
- Banggood Wnew heavy duty: https://www.banggood.com/Wnew-Woodworking-Heavy-Duty-Router-Lift-with-Aluminium-Router-Table-Insert-Plate-Woodworking-Tools-p-1963502.html
- AliExpress Wnew/JGC item: https://www.aliexpress.com/item/2251832270838858.html
- JGC factory listing: https://www.jgctools.com/goods/detail/291
- ZahyoX RL01 spec sheet (same family): https://zahyox.com/products/rl01
- Wnew reseller spec + price: https://levoite.com/products/wnew-heavy-duty-router-lift-router-table-lift-system
- SpeTool P01002 spec sheet: https://spetools.com/products/router-lift-p01002
- SpeTool on AliExpress: https://www.aliexpress.us/item/3256812598633138.html and https://www.aliexpress.com/item/1005010199458196.html
