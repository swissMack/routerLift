# Lift body comparison — quality, capability, fit

Compares the four candidates on 2026-09-04: the selected sauter FML-P and the three
full-size alternatives from `LIFT-ALTERNATIVES.md`. Sources are the two manuals in
`reference/`, the Sauter email and photo, and the listings cited in the alternatives doc.
Where a figure is inferred rather than stated it is marked *(inf.)*.

**One framing fact first.** The router is not yet bought (BOM: spindle motor 🛒). So the
lift and the router are one decision, not two. Each lift dictates a different router.

---

## 1. Specification side by side

| | **sauter FML-P** | **Wnew Heavy Duty** | **ENJOYWOOD Heavy Duty** | **SpeTool P01002** |
| --- | --- | --- | --- | --- |
| Origin | Germany, own manufacture | China (JGC factory), Banggood/AliExpress | China, Banggood house brand — same JGC design *(inf.)* | China-made, US company, EU warehouse |
| Router bore | Ø 43 mm Euro neck | Ø 107 mm + rings 65/69/80/88.9 | Ø 107 mm + rings 65/69/80/88.9 | 65–107 mm infinitely adjustable clamp |
| Max router | 5 kg, 1,100 W | Porter-Cable 7518 class (~1.8 kW, 6.5 kg) | same | same |
| Travel | **65 mm** | **100 mm** | 100 mm *(inf.)* | **107 mm** |
| Lead | **1.5 mm** (stated) | not stated — 1.5875 mm *(inf.)* | 1.5875 mm *(inf.)* | **1.27 mm** (20 TPI, stated) |
| Full-step resolution | 0.0075 mm | 0.0079 mm | 0.0079 mm | 0.00635 mm |
| `steps_per_mm` at 1/8 µstep | 1066.67 | 1007.87 | 1007.87 | 1259.84 |
| Insert plate | 306 × 229 × 9 mm, R6 — **its own size** | **300** × 235 × 10 mm | 298/300 × 235 × 10 mm | 298 × 235 × 9.5 mm |
| Plate standard | none | 9¼ × 11¾" (Kreg / JessEm) | same | same |
| Lift mass | 2.9 kg | ~10 kg | ~10 kg *(inf.)* | ~9 kg |
| Guide | 2 columns, knurled column clamp | 2 polished columns in bearing seats | same | 2 columns, double-sealed linear bearings |
| Nut | steel screw in bronze *(inf.)* | bronze nut, bolted, 3 screws | same | not stated |
| Holds unpowered | **Self-locking**, ~2.3° lead angle | **No** — PEEK/spring friction brake against "sinking under resonance" | same design *(inf.)* | "locking mechanism eliminates vibration drift" — a brake, same idea |
| Lower screw end | **Hex socket in a bearing block, driveable — confirmed by Sauter** | **Bare thread, unsupported, no feature — manual figs 2-1, 3-6, 5-1** | same *(inf.)* | same architecture *(inf.)* |
| Top drive | SW5 hex through plate | 10/13 mm hex via crank | same | crank + zeroing ring |
| Dust port | no | no | no | **yes** (P01003 hood) |
| DRO option | no | yes (optional) | no | no |
| Documentation | DE manual, 2 pages of data | CN/EN manual, 24 pp, exploded assembly figures | none found for this model | EN manual + full spec table |
| Warranty / support | German maker, spares catalogue, trading | Banggood seller | Banggood seller | 365-day, 90-day refund, DE warehouse |
| Reviews seen | none on this model | 51 on Banggood (5.0), 12 at reseller | **0** on the heavy-duty page (684 on the trim GD7) | 44 on maker site |
| Price seen | €329 B-stock / €378 | ~US$520 (reseller; Banggood not rendered) | US$290 | US$325 |
| Ships from | DE | CN or **CZ** | CN | CN or **DE** |

---

## 2. Quality

Ranked on what can be verified today, not on brand feel.

| Rank | Lift | Why |
| --- | --- | --- |
| 1 | **sauter FML-P** | German manufacture, spares ecosystem, a self-locking screw the maker trusts without a brake, and a lower hex the maker states is a drive input. Lightest by far (2.9 kg) — a sign of a simpler mechanism, not a weaker one. B-stock is the only quality unknown |
| 2 | **SpeTool P01002** | Only one of the three imports with a full published spec table, sealed linear bearings, a warranty you can invoke in Europe, and a DE warehouse. Same architecture as the Wnew, so the same brake caveat |
| 3 | **Wnew** | Established JGC design, reviewed as heavy and well made, bronze nut, bilingual manual with assembly figures. But the maker fitting a friction brake tells you the mechanism creeps under vibration unbraked. Lead unstated |
| 4 | **ENJOYWOOD** | Almost certainly the same JGC lift under a house brand, but nothing verified: no manual, no reviews on this model, specs not rendered. Cheapest for a reason — you are the QA |

A UK Workshop thread titled "Enjoywood router lift depth walking" exists for the maker's
trim-router lift. Different model, same maker, same failure the Wnew brake exists to hide.

---

## 3. Capability against the spec

| Requirement | FML-P | Wnew / ENJOYWOOD | SpeTool |
| --- | --- | --- | --- |
| MOT-01 resolution ≤ 0.01 mm | ✅ 0.0075 | ✅ 0.0079 | ✅ 0.0064 |
| MOT-02 repeatability | ✅ direct coupling, no belt | ⚠️ belt in the chain | ⚠️ belt in the chain |
| MEC-01 travel ≥ 75 mm | ❌ 65 mm | ✅ 100 mm, **~80 mm after the pulley** | ✅ 107 mm, ~87 mm after the pulley |
| MEC-02 hold unpowered | ✅ mechanism | ❌ needs brake or holding current | ❌ same |
| Drive from below (Rev A) | ✅ confirmed | ❌ belt from the side | ❌ belt from the side |
| Router power for large bits | ⚠️ ≤ 1,100 W | ✅ ~1.8 kW class | ✅ same |
| Dust extraction at the lift | ❌ | ❌ | ✅ |
| Bit change above table | via SW5 + spindle lock | ✅ crank | ✅ crank |

Both Rev A findings survive on every lift: ~0.15 N·m needed, TB6600 at 1.0–1.4 A/phase.
On the three imports add the brake's drag if it is left set, or hold with current.

---

## 4. Fit — what router each lift actually puts under a Swiss table

This is where "takes full-size routers" needs unpacking. The 88.9 mm and 107 mm
carriages are sized for North-American fixed-base motors: Bosch 1617, DeWalt 618,
Porter-Cable 690/7518. Those are **120 V** models. 230 V versions are scarce to
non-existent — verify before assuming one can be bought here.

What fits each lift on 230 V:

| Lift | Realistic 230 V router |
| --- | --- |
| FML-P (Ø 43) | AMB/Kress 1050 FME (1,050 W, ~1.7 kg), Suhner UAK 30, Mafell FM 1000. Continuous-duty spindle motors with soft start and speed control — the CNC-router class |
| Wnew / ENJOYWOOD (107 + ring) | **65 ring:** Makita RT0702, Bosch GKF 600, Katsu — 710 W trim routers. **69 ring:** DeWalt D26200 class, 900 W — verify the diameter, it is inferred from the DWP611. **88.9 ring:** only the Devon 1316-1, an obscure Chinese 230 V router. **80 ring:** a VFD spindle — **ruled out**, no inverter in this build. No 43 mm ring exists |
| SpeTool (65–107 clamp) | Same as above — **dropped on price** |

Full-size European routers — Triton TRA001, Bosch GOF 1600, Makita RP2301, Festool OF —
are plunge machines whose motors do not come out of the base. They cannot go in a
carriage lift at all.

So on 230 V without a VFD, **a Ø 107 lift carries a 710–900 W compact router.** That is
*less* power than the FML-P's 1,100 W Ø 43 spindle motor, not more. The imports' one
real gain over the FML-P is travel (100 mm) and the standard plate — the "full-size
router" advantage does not exist on this mains supply.

Other fit points:

- **Plate.** The three imports share the 9¼ × 11¾" standard: swap-compatible with Kreg,
  JessEm, Incra tables and phenolic blanks. The FML-P's 306 × 229 is its own size — a
  one-off cutout, no later swap.
- **Table.** 9–10 kg lifts want a braced table; 2.9 kg does not.
- **Fabrication.** FML-P: one bracket, one coupling, one hex stub. Imports: bracket,
  two pulleys, belt, tensioner, and a pulley that grips a threaded screw (split clamp or
  threaded bore with jam nuts).
- **Import.** CZ (Wnew) and DE (SpeTool, Sauter) warehouses avoid CN post; Swiss VAT
  applies to all.

---

## 5. Verdict

Two coherent packages, not four lifts:

**Package A — sauter FML-P + Ø 43 mm spindle motor.** The design as built. Direct
drive below, self-locking, best documented, least fabrication, lightest. Costs: 65 mm
travel (MEC-01 must be revised to ≥ 60 mm, deliberately), ≤ 1,100 W, no dust port, a
non-standard plate.

**Package B — ENJOYWOOD Heavy Duty (US$290) + Ø 69 DeWalt D26200 class (900 W) or
Ø 65 Makita RT0702 (710 W).** The cheapest 107 carriage, with a compact router in a ring.
Gains 100 mm travel (~80 mm after the belt pulley) and the standard plate. Costs: belt
drive redesign, holding current or brake for MEC-02, an unstated lead, a router with
*less* power than Package A, and a lift nobody has reviewed. SpeTool is out on price; the
Wnew is the same lift at nearly twice the money.

**Package C — ENJOYWOOD GD7 PRO (~US$180, 65/69 mm, 684 reviews) + trim router.** The
cheap route if 710 W and 60 mm travel are enough. Fails MEC-01 worse than the Sauter, and
the "depth walking" thread is about exactly this model.

**Recommendation: Package A.** With the VFD ruled out, the imports lose their only
argument — router power — and keep only travel, which they then spend a fifth of on the
belt pulley. The FML-P drives from below without a belt, holds without a brake, and takes
the most powerful router of the three packages. If Sauter's reply on screw torque is
unfavourable, Package B is the fallback.

Open before either purchase:

1. Sauter: permissible screw torque, lower hex size (asked 2026-09-04).
2. **Is there a router already in hand?** If so its motor diameter decides this outright.
   If not, Package A's AMB/Kress 1050 FME is the router to price.
3. MEC-01: revise to ≥ 60 mm, deliberately, in Rev H.
