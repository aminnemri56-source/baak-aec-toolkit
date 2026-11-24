"""Per-room reference images for Codex (07/11/2026), on top of the level refs and the exterior photo:
- machine: official photos of the exact machine model in the room ("SHOW MACHINES TO CODEX [SO IT] UNDERSTANDS"),
- design: the architect's validated esquisse of a feature of the room (RPM: esquisse 5D, perforated orange screen + video screen),
- pose: real classes from Pinterest showing how people are placed ("CHECK PINTEREST FOR POSITION AND PUT THEM IN THE INPUT CODEX").
Attach order for a hero job: render, level refs, machine refs, design refs, pose refs, exterior (last)."""
import os
import re

M = r"D:\DCE SITE\ARCHITECTURE\VISUELS\_REF_MACHINES"
P = r"D:\DCE SITE\ARCHITECTURE\VISUELS\_REF_POSITIONS"
E = r"D:\DCE SITE\ARCHITECTURE\ESQUISSES\ESQUISSES 3D\PROPOSITIONS 06 11 2026"
S = r"D:\DCE SITE\ARCHITECTURE\VISUELS\_REF_STYLE_SDC"
ROOM_REFS = {
    "PIL": dict(machine_name="Technogym Reform pilates reformer",
                machine=[os.path.join(M, "PIL_machine_1_technogym_reform.jpg"), os.path.join(M, "PIL_machine_2_technogym_reform.jpg")],
                design=[], design_what="",
                pose=[os.path.join(P, "PIL_pos_1.jpg"), os.path.join(P, "PIL_pos_2.jpg")]),
    "RPM": dict(machine_name="Technogym Group Cycle indoor bike",
                machine=[os.path.join(M, "RPM_machine_1_group_cycle_rider.jpg"), os.path.join(M, "RPM_machine_2_group_cycle_class.jpg")],
                design=[os.path.join(E, "ESQUISSE PROPOSITION 5D - RPM - ECRAN TOLE PERFOREE.png")],
                design_what=("the RPM wall as validated (esquisse 5D): the full-height orange perforated steel screen in front of the stair with RIDE. SWEAT. REPEAT. "
                             "cut through it (the black stair visible inside the letters and faintly through the perforations), PROJECT · RPM STUDIO cut vertically on its right edge, "
                             "and the vertical LED video screen with the class data at the back left"),
                pose=[os.path.join(P, "RPM_pos_1.jpg"), os.path.join(P, "RPM_pos_2.jpg")]),
    "SDC": dict(machine_name="", machine=[], design=[os.path.join(S, "sdc_ceiling_render_ref.png")],
                design_what="the salle de cours ceiling as rendered, the architect's choice (a large white rectangular light panel in every coffer, folded pyramid facets in light warm orange, soft gradients, hairline seams; never red, never small spots)",
                # 08/11 "NO STABLE WALL" / "LETS MAKE DES ESQUISSE TO PUT WITH OUR RENDER IN THE INPUT": one esquisse per camera,
                # drawn from the exact Vantage camera (D:/PROJECT_work/esq_sdc_cam/esq_sdc_cam.py), attached as a design image
                cam_esq=os.path.join(S, "ESQ_CAM", "ESQ_{view}.png"),
                pose=[os.path.join(P, "SDC_pos_1.jpg"), os.path.join(P, "SDC_pos_2.jpg")],
                # 07/11 "MATCH THEM STYLE" -> 08/11 "MORE CINEMATIC, ON THE LEVEL OF THE CARDIO RENDERS": the approved cardio photos are the level
                style=[os.path.join(r"D:\DCE SITE\ARCHITECTURE\VISUELS\_REF_NIVEAU_CARDIO", f) for f in ("cardio_21.png", "cardio_29.png", "cardio_30.png", "cardio_32.png")],
                light=("a cinematic real photograph at the level of these approved cardio photographs: deep true blacks and rich shadows, strong clean contrast, warm amber and golden sunlight "
                       "raking through the big windows (soft natural edges, never a checkerboard grid) against cool daylight, luminous glowing light panels, honey oak and the light warm orange ceiling rich, "
                       "neutral whites and natural skin (no orange cast), crisp micro-detail, faint film grain; small real-life imperfections in mats, towels, props and floor wear; the room bright where the light falls, "
                       "never faded, flat, grey, plastic or cartoonish; wherever the cardio floor shows through the glass partitions it is exactly the cardio of these photographs (black machines, copper perforated columns, "
                       "black lattice ceiling with LED lines)")),
}


def room_style(name):
    """(style images, light text) when a room has its own approved style, else ([], "")."""
    r = _room(name) or {}
    return [p for p in r.get("style", []) if os.path.exists(p)], r.get("light", "")


def style_text(n_style, light):
    return (f"IMAGES 2 TO {n_style + 1} ARE PHOTOGRAPHS OF THIS SAME GYM THAT THE ARCHITECT APPROVED: MATCH THEIR PHOTOGRAPHIC LEVEL EXACTLY: {light}. "
            "Take their light, colour grade, warmth, contrast and photographic finish; take nothing else (not their people, poses, props or framing: those come from image 1 and this brief).\n\n")

SHOW_MACHINES = ("SHOW THE MACHINES: the machines are the subject of the photograph and people must never hide them. The machine nearest the camera "
                 "stays empty and fully visible from end to end; about half of the machines in view stay free; on an occupied machine the frame, carriage, "
                 "foot bar, handlebar and seat stay readable. Fewer people, well placed, rather than a crowd covering the equipment.")


def _room(name):
    return next((v for k, v in ROOM_REFS.items() if k in name), None)


DESIGN_VIEWS = {"RPM": ("RPM_4", "RPM_6")}   # the 5D esquisse goes only to views that really show the 5D screen


def room_refs(name):
    """(machine refs, design refs, pose refs) that exist on disk for this view."""
    r = _room(name)
    if not r:
        return [], [], []
    ok = lambda L: [p for p in L if os.path.exists(p)]  # noqa: E731
    key = next(k for k in ROOM_REFS if k in name)
    dv = DESIGN_VIEWS.get(key)
    design = ok(r["design"]) if (dv is None or any(v in name for v in dv)) else []
    ce = cam_esq(name)
    return ok(r["machine"]), ([ce] if ce else []) + design, ok(r["pose"])


def cam_esq(name):
    """The architect's esquisse drawn from this very camera (same framing as the render), if there is one."""
    r = _room(name) or {}
    if not r.get("cam_esq"):
        return None
    m = re.search(r"([A-Z]+_\d+)$", name)
    p = r["cam_esq"].format(view=m.group(1)) if m else ""
    return p if p and os.path.exists(p) else None


CAM_ESQ_TEXT = ("{rng} IS THE ARCHITECT'S ESQUISSE OF THIS SAME CAMERA: the same framing as image 1, pixel for pixel, drawn from the 3D. "
                "The walls, wall niches, ceiling colour and columns of the photograph follow it EXACTLY: every vertical line (oak panel edges, niche frames) "
                "at the same place in the frame, the same number of niches and panels, the same widths; the ceiling in its orange; the columns where it puts them. "
                "Where the render and this esquisse differ on the walls or the ceiling colour, the esquisse wins. People, hammocks, mats, props on the floor, glazing view and light "
                "come from image 1 and this brief. It is a flat drawing: take its design, never its flat colours, plain fills or drawing style." + "\n\n")


def _rng(i, n):
    return f"IMAGE {i}" if n == 1 else f"IMAGES {i} TO {i + n - 1}"


def refs_text(name, first_index, n_machine, n_pose, n_design=0):
    """Text for the machine, design and pose images, numbered from first_index (the image right after the level refs)."""
    r = _room(name) or {}
    out, i = "", first_index
    if n_machine:
        out += (f"{_rng(i, n_machine)} SHOW THE REAL MACHINE of this room, the {r.get('machine_name', 'machine')}, with a person using it correctly. Study them to understand "
                "every part of the machine and exactly where a body goes on it. The machines in the photograph stay those of image 1 (same model, colour, "
                "place and orientation); take nothing else from these images.\n\n")
        i += n_machine
    if n_design and cam_esq(name):
        out += CAM_ESQ_TEXT.format(rng=_rng(i, 1))
        i += 1
        n_design -= 1
    if n_design:
        out += (f"{_rng(i, n_design)} IS THE ARCHITECT'S VALIDATED DRAWING of {r.get('design_what', 'a feature of this room')}. Wherever that feature is in view, the photograph shows it "
                "built exactly like this drawing: same material, colour, letters, cut-outs, proportions and screen content, at the place image 1 gives it. It is a drawing: take its "
                "design, never its drawing style, its labels, numbers, title block or plan.\n\n")
        i += n_design
    if n_pose:
        out += (f"{_rng(i, n_pose)} ARE POSITION REFERENCES from real classes: copy only how the people are placed: one per machine or mat, aligned with it, "
                "all doing the same exercise in sync, facing the coach. Do not copy their room, equipment colour, clothes, light, framing or style.\n\n")
    if "RPM" in name:   # the RPM is a full class (user, 07/11): riders on almost every bike
        return out
    return out + SHOW_MACHINES + "\n\n"
