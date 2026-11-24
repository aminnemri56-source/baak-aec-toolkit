"""Codex briefs, "unlimited level" (07/11/2026): locked inventory, allowed changes only, per-view 3D errors to remove,
room-specific people and exercises, then a mandatory self-check against a fault checklist with up to 3 attempts.
Used by make_codex_jobs.py (hero photos) and cinematic_shots.py (shots from a finished hero)."""
from codex_refs import refs_text, room_refs, room_style, style_text, SHOW_MACHINES  # noqa: F401  (machine + position references per room)

ORANGE = "#EE5A1E"
# Exterior reference photo, attached LAST to every job (the user's pick, 07/11): the real look of the street outside.
EXTERIOR_IMG = r"D:\DCE SITE\ARCHITECTURE\VISUELS\_REF_EXTERIEUR\exterieur_boulevard_site.png"
EXTERIOR_REF = ("THE LAST ATTACHED IMAGE IS THE REAL EXTERIOR of the site: it appears ONLY where image 1 has real glazing onto the outside, never on a screen, wall, blind or panel; every view through that glass shows this boulevard as it would be seen "
                "from this floor and in this camera's direction: the same terracotta-pink ochre apartment buildings with balconies, the same olive "
                "trees, date palms and green verges, the street, pavements and lamp posts. Take its CONTENT only, never its look: that photo is HDR and "
                "oversaturated. Seen from inside through the glass, with the camera exposed for the interior, the outside is paler, softer, slightly out of focus, "
                "partly blown out by the sun, with faint reflections on the glass, and a pale blue sky. It is only the outside view: "
                "it never changes the room, and the building's own terrace or planters right behind the glass stay as image 1 shows them.\n\n")
# Look = finesse and clarity of the Behance ROOF GYM visuals the user gave (07/11), after "too cartoonish".
PHOTO = ("A BRIGHT, WELL-LIT SPACE (the user insists): generous exposure, the whole room fully and evenly lit, open shadows, no dark corners, no gloomy areas, a light airy feeling, like a bright daytime photograph of the space. "
         "THE LOOK, FINESSE AND CLARITY: the level of the reference images: crystal-clear, crisp and refined, like a top architectural visualisation "
         "that passes for a photograph. Soft, diffuse natural daylight that wraps the room with gentle soft shadows (no harsh dappled sun patches all over the floor); "
         "a calm, natural, slightly desaturated palette; true whites and soft deep blacks; every material precise and believable: fine oak grain, matt black "
         "powder-coated steel, soft upholstery, clean glass with subtle reflections; clean, uncluttered surfaces; the exterior bright, soft and a little hazy, "
         "exposed for the interior. The PROJECT orange is deep and matt, never neon. Not a cartoon, not an illustration, not a video game: no oversaturated colour, "
         "no glow, no bloom, no halo, no HDR, no plastic skin, no oversharpening, no heavy grain or noise.")
# Project exterior in words (PROJECT, corner Av. Moulay Al Hassan x Rue Imam Chafai, Gueliz-Hivernage, Site). Edit for another project.
EXTERIOR = ("the real site, Gueliz-Hivernage in Site, seen from this floor of the building: first the building's own terrace "
            "or ground exactly as image 1 shows it beyond the glass (gravel, planters), then a wide city avenue lined with tall date palms "
            "and green orange and olive trees, and modern three-to-five-storey buildings with flat roofs rendered in the Site "
            "terracotta-pink ochre plaster (the city's red ochre colour), dark or white window frames, balconies, shop fronts at street level, "
            "a few cars; a deep clear blue sky and strong warm Site sun. No minaret, no medina walls or ramparts, no water, "
            "no pool, no white or grey European apartment blocks, no landmark")
HIDDEN = ("HIDDEN LIGHT (the user insists on it): every concealed LED line of image 1 stays ON and clearly visible, even in daylight: ceiling coves and perimeter lines, the warm glow under the slatted band below the planters, the strips inside the shelving bays, lines under benches, podiums and along the floor. Warm white about 3000 K, continuous and even, with a soft gradient wash on the surface it lights and a gentle glow on the floor, like the glowing pebble strips in the reference images; never switched off, never faded out by the daylight, never turned into hard neon or coloured light. Do not add LED lines where image 1 has none.")
SOURCES = ("LIGHT HAS A VISIBLE SOURCE AND THE MODEL IS CLEAN (the user: light source not seen, dark glass, bad modelling): every patch of sunlight must come from a window that can really cast it (visible, or obviously just outside the frame on that side); if there is no such window, there are no sun patches and the light comes from the luminaires and glazing you can see, which visibly glow and cast soft pools of light. Glass partitions and glazing are clear and transparent (only slightly reflective), never smoked or dark. Geometry is clean: columns are straight perfect cylinders, perforated metal has a regular grid of round holes, mats are separate flat rounded rectangles in a regular layout, ceiling modules show no dark joint lines, shelves and frames are straight; nothing warped, bulging, merged or overlapping.")
SCREENS = ("SCREENS AND WALLS STAY: every video screen, TV and display of image 1 stays exactly where it is, same size, switched on and showing its picture (class data, logos, graphics); every wall, perforated panel, blind and door stays a wall, panel, blind or door. Never turn a screen, a wall or a panel into a window or an outdoor view, and never remove a screen.")
MACHINES = ("MACHINES ARE UNTOUCHABLE: every machine (reformers, bikes, treadmills, benches, racks, towers) stays exactly as in image 1: "
            "same model, same shape, every part (frames, foot bars, rails, carriages, shoulder blocks, straps, handles, pedals, screens), "
            "same position, same orientation, same count, same colour. Do not redraw, simplify, rebuild, restyle, move, add or remove any machine "
            "or machine part, even if a part looks odd or very close to the lens. Only their surfaces become photographic (real matt finish, real upholstery); "
            "black stays black, sunlight never turns it grey, white or silver. People use the machines as they are and never hold a machine part as a prop.")
REFS = [  # images 2.. : level only (finesse, clarity). Behance ROOF GYM by elhussieni, given by the user 07/11; Pinterest pins dropped (too AI/cartoonish).
    r"D:\DCE SITE\ARCHITECTURE\VISUELS\_REF_NIVEAU_BEHANCE_ROOFGYM\roofgym_07_people_treadmill.jpg",
    r"D:\DCE SITE\ARCHITECTURE\VISUELS\_REF_NIVEAU_BEHANCE_ROOFGYM\roofgym_08_people_space.jpg",
    r"D:\DCE SITE\ARCHITECTURE\VISUELS\_REF_NIVEAU_BEHANCE_ROOFGYM\roofgym_11_space.jpg",
]

ROOMS = {
    "PIL": dict(
        where="the Pilates reformer studio of the PROJECT premium gym in Site",
        design="round oak column and open oak shelving holding balls, rings, blocks and rollers (each in the colour image 1 gives it), warm oak floor, black steel ceiling grid with small black spots, and in every coffer between the black beams a pale panel softly lit by hidden LED coves (each panel glows warm white, brighter along its edges next to the beams; this ceiling light is always on), full-height black-framed glazing, black planters with green plants along the glass, a warm-lit vertical slat band under the planters, matt black reformers",
        people="Three to five people (women and one man) in black, charcoal and neutral sportswear, one per reformer, all doing the same exercise of the class at the same time (for example all in footwork: lying on the back, head on the headrest between the shoulder blocks, both feet on the foot bar), aligned with their reformer; one instructor stands in an aisle facing them, correcting one person with a light hand gesture.",
        add="if the oak storage unit with open shelves (balls, rings, blocks, rollers) is in view: clear frameless glass doors on every bay, flush with the front of the oak frame, thin polished edges, small black handles, real reflections, the contents fully visible behind; glass on that unit only",
        remove="if visible: the thin horizontal white-and-black bar that runs across the room at chest height in front of the glazing (the glass, the view and anything behind continue cleanly)",
    ),
    "RPM": dict(
        where="the indoor cycling studio of the PROJECT premium gym in Site",
        design=f"black room, black bikes in rows facing the instructor; the floor is a BLACK SPECKLED sports floor like the cardio floor (black with fine light grey and white flecks, matt), never pale grey or white; the triangular ceiling lattice is dark brushed bronze metal (deep brown-gold, satin, a little soft reflection on the beam edges, strongly contrasted against the matt black ceiling), never orange wood, with its linear LED lights; every wall graphic is BLACK AND ORANGE ONLY (PROJECT): what the render shows brown, grey-brown or dark becomes matt black, what it shows beige, sand, ochre or yellow becomes the PROJECT orange {ORANGE}; no brown, no beige, no yellow on the walls; the room has three features, each drawn ONLY where image 1 shows it and NEVER added where this camera does not see it (read image 1 and the THIS VIEW notes): (1) the TYPOGRAPHIC WALL: a matt black wall with a big orange diagonal band and huge letters RIDE. and SWEAT. in white and REPEAT. in orange; (2) the 5D SCREEN: a full-height screen of orange perforated steel sheet standing in front of the stair, RIDE. SWEAT. REPEAT. cut through it in dark letters, PROJECT · RPM STUDIO cut vertically on its edge; (3) the STAIR CLADDING: dark perforated sheet metal with two vertical warm LED lines, with the tall vertical LED video screen (class data) mounted between those two LED lines; never put the video screen anywhere else and never turn the typographic wall into the perforated screen; the instructor podium, the ceiling and lights exactly as image 1; the RPM studio is a closed room: the stair, the stair walls and every wall around the bikes are solid walls: the stair wall is clad in dark perforated sheet metal (habillage en tole perforee: dark grey-black steel panels with fine regular round holes, matt) with its hidden light: two concealed warm LED lines running along the cladding, always on, glowing and washing the perforated metal softly, and the other walls carry the orange screen and the wall graphics; never windows, and there is no outdoor view in this room",
        no_ext=True,
        people="A LIVELY CLASS, NOT PACKED (the user: reduce people, don't change machine places): EXACTLY 9 RIDERS in the view (the user: keep like 9 people on the RPM), ALL FACING ONE DIRECTION, the direction every bike faces in image 1 (the user: one direction), spread through the rows, each sitting on one of the bikes exactly where it stands in image 1 (never move, add, remove or turn a bike to place a person; the bikes nearest the camera stay empty), all different individuals riding the same part of the class together (all seated, or all standing on a climb): hands on the handlebars, feet on the pedals, facing the instructor, mid-effort, sweat and focus; the instructor on the podium bike faces them.",
    ),
    "SDC": dict(
        where="the group class room of the PROJECT premium gym in Site",
        design="WEST WALL (08/11, the user: no stable wall, generalise these vertical lines): ONE fixed rhythm along the whole wall exactly as the architect's camera esquisse: full-height natural oak panels about 46 cm wide with fine vertical grain, alternating with black-framed niches about 60 cm wide (10 niches), each niche backlit warm white with 4 thin black shelves and the same props top to bottom (a ring, cork blocks, two balls, two balls, rolled towels); no LED line at the foot of this wall; no other volume, block, slats or terracotta on this wall; COLUMNS (the user: poteaux real as the renders): perforated metal sleeves exactly as image 1: dark bronze-brown satin metal, regular grid of small round holes with a faint warm glow, soft vertical highlight, thin black strips at top and base, never mosaic or black tiles; CEILING LIKE THE RENDER (the user, 08/11: 'ceiling should be orange no red', 'ceiling like that' on the render): in every coffer a LARGE white rectangular light panel (about half the coffer width, the render's grid), folded pyramid facets in a LIGHT WARM ORANGE (peach-orange lit, warm orange in shade, never red, rust, brick or burgundy, never small square spots): crisp folded pyramid coffers, each with a glowing rectangular diffuser in its recess, light running down the facets in strong soft gradients, only very fine hairline seams (never thick black joints), oak floor, black podium, the mats and props exactly as image 1 (same colour, count and place), orange aerial yoga hammocks, exactly as image 1; the glazing behind the podium carries a ONE-WAY VISION film: its printed yoga / PROJECT visual is seen only from the street outside, so from inside it is NEVER visible: the glass reads as slightly darkened glazing with a very fine dark dot screen, through which the real outdoor view is seen (softly dimmed, as through a one-way film)",
        people="A class of real women and men on the mats, one person per mat, all facing the teacher on the black podium and all doing the same pose the teacher shows (for example all in warrior II, or all in downward dog), with small natural differences; one or two in the orange aerial yoga hammocks if they are in view; the teacher on the podium facing the class.",
    ),
}
DEFAULT = dict(where="the training floor of the PROJECT premium gym in Site", design="exactly as image 1",
               people="Real athletes in black sportswear on the machines in view, each using the machine the right way, absorbed.")


def room_for(name):
    return next((v for k, v in ROOMS.items() if k in name), DEFAULT)


CHECK_HERO = [
    "FRAMING: same camera position, lens, crop, horizon and vanishing lines as image 1; verticals straight.",
    "INVENTORY: every object of image 1 is still there, same place, same size, same count; nothing added except the requested design addition and small personal items next to a machine (a water bottle, a folded towel) (no new lamp, plant, furniture, machine, prop, sign, text or logo).",
    "ERRORS: each listed 3D error is gone completely and what was behind it continues cleanly (no smear, ghost or gap).",
    f"COLOURS: machines keep their colour from image 1 (black stays black); brand orange is {ORANGE}, never yellow; wood stays warm oak; every accessory keeps its colour from image 1; no global orange, sepia or teal cast.",
    "LIGHT AND EXTERIOR: bright natural daylight; the view outside is the real Site Gueliz avenue (terracotta-pink ochre buildings, date palms, blue sky; no white European blocks, no minaret, no medina, no water); each light keeps its colour from image 1; not dark or moody, interior not blown out.",
    "PEOPLE: the right count; each one does a real exercise that fits the machine or mat under them; hands and feet touch real parts; correct anatomy (two arms, two legs, five fingers, joints bending the right way); nobody floats, merges with a machine or another body, or holds an object that is not in image 1; nobody looks at the camera; nobody appears inside or behind shelving or a cabinet; they do not hide the main design.",
    "HUMAN AND POSITIONS: every person is a different individual; it reads as a real class: everyone does the coach's exercise, each on their own reformer, bike or mat, aligned with it and facing the coach, in the exact position described in POSITIONS; nobody sits on a frame edge, across a machine, on the floor or facing the wrong way.",
    "GRAVITY: nothing floats: every foot, knee, hip, back and hand rests on the floor, a carriage, a mat or a bar; every ball, roller, block and ring sits on a shelf or the floor; each contact has its real contact shadow; nothing hangs in the air or sinks into a surface.",
    "HIDDEN LIGHT: every concealed LED line of image 1 (coves, under the planters, inside the shelving, floor and bench lines) is on, warm, continuous and clearly visible with its soft wash; none missing, none added.",
    "SHOW THE MACHINES: no person hides a machine; the machine nearest the camera is empty and fully visible; about half the machines in view are free; every occupied machine stays readable.",
    "SCREENS AND WALLS: every screen of image 1 is still there, on, with its picture; no screen, wall, blind or panel became a window or a view; the outside appears only through real glazing.",
    "SOURCES AND GEOMETRY: every light patch has a visible source; glass is clear, not dark; columns straight, perforations regular, mats separate and flat, no ceiling joints, nothing warped or merged.",
    "MACHINES: every machine identical to image 1: same model, every part, position, orientation, count and colour; nothing redrawn, simplified, moved, added, removed, melted, bent, stretched or duplicated.",
    "TEXT: no invented or garbled text; existing signs keep their exact letters.",
    "FINESSE AND CLARITY: as crisp, clean and refined as the reference images; soft diffuse daylight, calm natural colour, matt orange, believable materials and skin; no cartoon, illustration, plastic, glow, oversaturation, HDR or heavy grain.",
    "FORMAT: landscape, same aspect ratio as image 1, the largest size available.",
]

HUMAN = ("THINK LIKE A HUMAN PHOTOGRAPHER (the user's rule): one real moment of a real class in a real club, photographed candidly. "
         "Every person is a different individual: different faces, ages (about 22 to 55), body types, skin tones and hair (straight, curly, short, tied, grey at the temples); "
         "never the same woman or man twice. Outfits differ within a sober palette: black, charcoal, grey, white, sand, olive, navy. "
         "IT IS A CLASS: everyone follows the coach and does the same exercise of the sequence at the same time, with only small natural differences in timing, "
         "range and effort; nobody sits chatting, wanders, rests on the floor or does something else. "
         "GRAVITY: nothing floats. Every foot, knee, hip, back and hand rests on the floor, a carriage, a mat, a pedal or a bar with a real contact shadow; "
         "every ball, roller, block and ring sits on a shelf or the floor; nothing hangs in the air or sinks into a surface.")
POSITIONS = ("POSITIONS ON THE EQUIPMENT (get them exactly right, as a real instructor would): "
             "A REFORMER is a long low bed: the padded carriage slides along the frame; the shoulder blocks and headrest are at one end of the carriage; "
             "the foot bar rises at the other end; the ropes with hand straps come from the pulleys behind the shoulder blocks. A person on a reformer is always "
             "on the carriage and aligned with its length, never across it, never sitting on the frame edge, never on the foot-bar end facing the wrong way: "
             "lying on the back with the head on the headrest between the shoulder blocks and both feet on the foot bar (footwork), or lying on the back with the hands in the straps, "
             "or kneeling on the carriage facing the pulleys with a strap in each hand, or with both hands on the foot bar and the feet against the shoulder blocks (elephant, knee stretch). "
             "A BIKE: seated on the saddle or standing on the pedals, both hands on the handlebar, both feet on the pedals, facing the handlebar and the instructor. "
             "A MAT: the whole body on the person's own mat, aligned with the mat, facing the teacher on the podium or the front of the room. "
             "The coach stands on the floor in an aisle (or on the podium in the group room), facing the class. "
             "If a position cannot be shown clearly, leave that machine or mat empty: two people placed right are better than five placed wrong.")

PROCESS = (
    "METHOD (mandatory):\n"
    "1. Study image 1 first. Write INVENTORY.txt in this folder: the zones of the image from left to right and every object, material and colour that must stay.\n"
    "2. Generate the photograph with the imagegen skill, using image 1 as the base image to edit.\n"
    "3. Open your result next to image 1 and go through the CHECKLIST item by item, honestly, zooming in on people, hands, machines and the listed errors.\n"
    "4. If any item fails, generate again with an instruction that names exactly what failed and how to correct it. Up to 3 attempts in total. Keep the attempt with the fewest failures.\n"
    "5. Copy the kept image into this folder as photo.png. Write CHECK.txt: the number of attempts and, for the kept image, each checklist item with PASS or FAIL and a few words.\n"
    "Imagegen saving its source images in its own default folder is fine and expected. Do not run Python. Do not edit the image with code: every image comes from imagegen.\n"
)


def _refs_text(n_refs):
    if not n_refs:
        return ""
    return (f"IMAGES 2 TO {n_refs + 1} SET THE LEVEL, NOTHING ELSE: match their finesse and clarity: crisp, clean, refined, soft diffuse daylight, calm natural colour, believable people and materials. Take nothing from their content: no room, no ceiling, no furniture, no machines, no hammocks, no plants, no colours, no format, no watermark, no logo, no text.\n\n")


def hero(name, fixes=(), n_refs=0, ext=False, n_machine=0, n_pose=0, n_design=0, styled=False):
    """fixes: list of errors to remove, or {"remove": [...], "notes": [...]} (notes = view-specific instructions)."""
    r = room_for(name)
    notes = []
    if isinstance(fixes, dict):
        notes, fixes = fixes.get("notes", []), fixes.get("remove", [])
    fixes = list(fixes)
    if r.get("remove") and not fixes:   # room-wide error, unless the view lists its own
        fixes = [r["remove"]]
    add = r.get("add", "")
    errs = ""
    if fixes:
        errs = ("3D ERRORS TO REMOVE (the only objects you may take out; never a machine or a machine part):\n" + "".join(f"- {f}\n" for f in fixes) + "\n")
    if notes:
        errs += "THIS VIEW:\n" + "".join(f"- {n}\n" for n in notes) + "\n"
    checks = "".join(f"{i}. {c}\n" for i, c in enumerate(CHECK_HERO, 1))
    return (
        f"You are a senior architectural photographer and retoucher. Image 1 is my 3D render of {r['where']}. Turn this exact image into a crystal-clear real photograph taken on a bright day in soft, diffuse daylight.\n\n"
        f"LOCKED, identical to image 1: the camera, framing and perspective; the design: {r['design']}; every object with its place, size and count; every material and colour; every light and its colour; the ceiling, floor, walls, glazing and wood; screens and signs with their exact pictures and letters.\n\n"
        f"ALLOWED CHANGES, and only these: photographic realism of what is already there (real textures, real light falloff, soft contact shadows, real reflections in the glass); a real outdoor view only through the real glazing of image 1 (never through a screen, wall, blind, door or perforated panel) instead of the 3D background, slightly overexposed as in a real interior photograph, showing {EXTERIOR}; the people described below"
        + ("; the removal of the 3D errors listed below" if fixes else "")
        + (f"; this design addition requested by the architect: {add}" if add else "") + ".\n\n"
        + MACHINES + "\n\n" + SCREENS + "\n\n" + SOURCES + "\n\n" + errs +
        f"PEOPLE: {r['people']} Real skin, hair, hands and fabric, real body weight on the machines, not looking at the camera, not stock-photo models. People are only on the floor or on the machines, at a believable scale for their distance; never seen inside or behind shelving, cabinets or glass doors as if standing in them.\n\n"
        + HUMAN + "\n\n" + POSITIONS + "\n\n"
        f"COLOUR AND LIGHT: neutral white balance, clean generous exposure. Brand orange stays the PROJECT orange {ORANGE}, a deep red-orange, never yellow. Wall, ceiling and floor colours do not shift. No dark moody look, no orange cast.\n\n"
        + (style_text(n_refs, room_style(name)[1]) if styled else _refs_text(n_refs)) + refs_text(name, n_refs + 2, n_machine, n_pose, n_design) + (EXTERIOR_REF if ext else "")
        + (PHOTO.replace("Soft, diffuse natural daylight that wraps the room with gentle soft shadows (no harsh dappled sun patches all over the floor)", "The light of the style images: " + room_style(name)[1]) if styled else PHOTO) + " Straight verticals. " + HIDDEN + "\n\n"
        f"CHECKLIST:\n{checks}\n" + PROCESS
    )


SHOTS = {  # each shot has a no-people variant: when image 1 shows nobody, never add a person (PIL_6 / PIL_7, 07/11)
    "CU_85mm_zoom": "a cinematic 85 mm zoom on the person closest to the camera in image 1, mid-exercise: waist-up to full-body framing with the whole head in frame, eye level, shallow depth of field, the room behind softly blurred but readable. IF IMAGE 1 SHOWS NO PERSON: a cinematic 85 mm detail of its most beautiful element (joinery, materials, the hidden light, the machines), shallow depth of field, and no person at all",
    "CU_low_detail": "a low-angle cinematic detail at machine height: hands on the strap handles or the foot bar and feet on the machine, the person's face in frame or turned away (never cut through the head), the wood and the floor sharp in the foreground, the room in soft blur behind, real sunlight grazing the textures. IF IMAGE 1 SHOWS NO PERSON: a low-angle detail of the same materials and machines with the light grazing their textures, and no person at all",
    "CU_side_tele": "a cinematic side angle with a long lens from the side of the room, along the row of machines: telephoto compression, two or three of the same people mid-exercise overlapping in depth, natural relaxed poses, gentle bokeh on the nearest and farthest machines. IF IMAGE 1 SHOWS NO PERSON: the same long-lens side angle across the space of image 1, telephoto compression, and no person at all",
}

CHECK_SHOT = [
    "SHOT: it is the requested shot (lens, angle, framing); no head or face cut by the frame edge unless the shot asks for it.",
    "SAME PLACE: same room, materials, colours and lights as image 1; nothing invented (no new lamp, plant, furniture, machine, prop, sign, text or logo).",
    "SAME PEOPLE: the same faces, hair and clothes as in image 1; each one does a real exercise that fits the machine or mat; hands and feet on real parts; correct anatomy; nobody holds an object that is not in image 1.",
    f"COLOURS: machines matt black; brand orange {ORANGE}, never yellow; warm oak stays warm oak; no global cast.",
    "HIDDEN LIGHT: the concealed LED lines seen in image 1 stay on, warm and clearly visible.",
    "MACHINES: the same machines as image 1, every part kept, nothing redrawn, simplified, melted, bent, stretched or duplicated.",
    "GRAVITY: nothing floats; every body part and object rests on something with a real contact shadow.",
    "FINESSE AND CLARITY: crisp and refined like the reference images, real optical depth of field, calm natural colour, real skin; no cartoon, plastic, glow, oversaturation or HDR.",
]


def shot(where, shot_text, n_refs=0, ext=False):
    checks = "".join(f"{i}. {c}\n" for i, c in enumerate(CHECK_SHOT, 1))
    return (
        f"You are a senior architectural and lifestyle photographer. Image 1 is a finished photograph of {where}. Make a new photograph taken a moment later in the same room, same day, same light, by the same photographer: {shot_text}.\n\n"
        f"Everything in it is what image 1 shows: the same people with the same faces, hair and clothes, the same wood, floor, walls, ceiling, lights and colours; any view through the glass shows {EXTERIOR}. Brand orange stays the PROJECT orange {ORANGE}, never yellow. Do not invent machines, furniture, lamps, plants, props, signs, slogans or logos.\n\n"
        + MACHINES.replace("exactly as in image 1", "exactly as image 1 shows them, seen from the new angle") + "\n\n"
        + "GRAVITY: nothing floats: every foot, knee, hip, back and hand rests on the floor, a carriage, a mat or a bar with a real contact shadow; every ball, roller, block and ring sits on a shelf or the floor. The moment is candid and human, not a staged catalogue pose.\n\n"
        + _refs_text(n_refs) + (EXTERIOR_REF if ext else "")
        + PHOTO + " " + HIDDEN + " Landscape 3:2, the largest size available.\n\n"
        f"CHECKLIST:\n{checks}\n" + PROCESS.replace("Study image 1 first. Write INVENTORY.txt in this folder: the zones of the image from left to right and every object, material and colour that must stay.", "Study image 1 first: the people, their clothes, the machines and the room.").replace("Up to 3 attempts in total.", "At most 2 attempts in total (speed: the art director reviews every shot after you).").replace("using image 1 as the base image to edit", "with image 1 as the reference for the people and the room")
    )
