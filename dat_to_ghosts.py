import os
import json
import requests
import time
from nbtlib import nbt

PLAYERDATA_DIR = "./playerdata"
CACHE_FILE_TEMPLATE = "uuid_cache_{world}.json"
TAG = "nostalgia_ghost"
Y_OFFSET = 0.0

OUT_DIR = "./nostalgia_ghosts"
FUNC_DIR = f"{OUT_DIR}/data/ghosts/functions"
TAG_DIR = f"{OUT_DIR}/data/minecraft/tags/functions"


# ---------------- UUID → NAME ----------------

def load_cache():
    # use world folder name so different worlds get separate caches
    world = os.path.basename(os.path.abspath('.'))
    cache_file = CACHE_FILE_TEMPLATE.format(world=world)
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    world = os.path.basename(os.path.abspath('.'))
    cache_file = CACHE_FILE_TEMPLATE.format(world=world)
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=2)

def uuid_to_name(uuid, cache):
    if uuid in cache:
        v = cache[uuid]
        # cache may be either a name string or a dict with profile data
        return v if isinstance(v, str) else v.get("name")

    u = uuid.replace("-", "")
    r = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{u}")
    if r.status_code == 200:
        name = r.json().get("name")
        cache[uuid] = name
        return name

    return uuid  # fallback


def uuid_profile(uuid, cache):
    """Return (name, textures_value_or_None) and cache the result.
    Cache entry is stored as {"name": ..., "textures": ...} when textures found.
    """
    if uuid in cache:
        v = cache[uuid]
        if isinstance(v, dict):
            return v.get("name"), v.get("textures")
        else:
            # cache only contains a name string; attempt to fetch profile to get textures
            name_guess = v
            u = uuid.replace("-", "")
            r = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{u}")
            if r.status_code == 200:
                j = r.json()
                name = j.get("name") or name_guess
                textures = None
                props = j.get("properties", [])
                for p in props:
                    if p.get("name") == "textures":
                        textures = p.get("value")
                        break
                cache[uuid] = {"name": name, "textures": textures}
                return name, textures
            # can't fetch textures; return cached name
            return name_guess, None

    u = uuid.replace("-", "")
    r = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{u}")
    if r.status_code == 200:
        j = r.json()
        name = j.get("name")
        textures = None
        props = j.get("properties", [])
        for p in props:
            if p.get("name") == "textures":
                textures = p.get("value")
                break
        cache[uuid] = {"name": name, "textures": textures}
        return name, textures

    # fallback
    cache[uuid] = uuid
    return uuid, None


def names_to_uuids(names, cache=None):
    """Bulk-resolve a list of player names to UUIDs using
    Mojang's POST /profiles/minecraft endpoint.

    Returns a dict mapping name -> dashed-uuid (if found). If `cache` is
    provided it will be updated with uuid->name entries for any results.
    """
    if not names:
        return {}

    url = "https://api.mojang.com/profiles/minecraft"
    out = {}
    batch_size = 100
    for i in range(0, len(names), batch_size):
        batch = names[i:i + batch_size]
        try:
            r = requests.post(url, json=batch, timeout=10)
        except Exception:
            # network error
            time.sleep(0.5)
            continue

        if r.status_code != 200:
            # failed
            time.sleep(0.5)
            continue

        try:
            data = r.json()
        except Exception:
            time.sleep(0.5)
            continue

        for entry in data:
            raw = entry.get("id")
            name = entry.get("name")
            if not raw or not name:
                continue
            # format raw 32-char id into dashed UUID
            if len(raw) == 32:
                uuid = f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
            else:
                uuid = raw

            out[name] = uuid
            if cache is not None:
                cache[uuid] = name

        # be polite with Mojang API
        time.sleep(0.1)

    return out

# ---------------- ITEM HELPERS ----------------

def item_nbt(item):
    if not item:
        return "{}"
    return item.snbt()


def format_item_for_command(snbt_str):
    """Convert an SNBT compound like '{id:"minecraft:stone",Count:1b,tag:{...}}'
    into a command item token like 'minecraft:stone{Count:1b,tag:{...}}'.
    Returns None if input is empty or cannot be parsed.
    """
    if not snbt_str or snbt_str == "{}":
        return None

    s = snbt_str.strip()
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1]
    else:
        inner = s

    id_idx = inner.find('id:')
    if id_idx == -1:
        return None

    # find quoted id value
    q1 = inner.find('"', id_idx)
    if q1 == -1:
        return None
    q2 = inner.find('"', q1 + 1)
    if q2 == -1:
        return None

    item_id = inner[q1 + 1:q2]

    # rest of the string after the id
    rest = inner[q2 + 1:]
    parts = []
    cur = []
    depth = 0
    for ch in rest:
        if ch == '{':
            depth += 1
            cur.append(ch)
        elif ch == '}':
            depth -= 1
            cur.append(ch)
        elif ch == ',' and depth == 0:
            token = ''.join(cur).strip()
            if token:
                parts.append(token)
            cur = []
        else:
            cur.append(ch)
    last = ''.join(cur).strip()
    if last:
        parts.append(last)

    # clean parts: drop Count:..., unwrap tag:{...} into its inner content
    cleaned = []
    for p in parts:
        p = p.lstrip()
        if p.startswith(','):
            p = p[1:].lstrip()
        if p.startswith('Count:'):
            continue
        if p.startswith('tag:'):
            # find first '{' in p
            b = p.find('{')
            if b != -1:
                # extract inner braces content (assume balanced within this token)
                inner_content = p[b+1:-1].strip()
                if inner_content:
                    cleaned.append(inner_content)
            continue
        # ignore empty tokens
        if p:
            cleaned.append(p)

    if not cleaned:
        return item_id

    final = ', '.join(cleaned)
    return f"{item_id}{{{final}}}"

def get_armor(inv):
    # Minecraft armor slots: 100 boots, 101 leggings, 102 chest, 103 helmet
    armor = {100: None, 101: None, 102: None, 103: None}
    for it in inv:
        slot = int(it["Slot"])
        if slot in armor:
            armor[slot] = it
    # order: feet, legs, chest, head
    return [
        item_nbt(armor[100]),
        item_nbt(armor[101]),
        item_nbt(armor[102]),
        item_nbt(armor[103]),
    ]

def get_held(inv, selected):
    for it in inv:
        if int(it["Slot"]) == selected:
            return item_nbt(it)
    return "{}"

# ---------------- COMMAND ----------------

def summon_cmd(x, y, z, yaw, name, held, armor, idx):
    # add an index tag for ordered teleporting: ghost_1, ghost_2, ...
    return (
        f'summon armor_stand {x:.3f} {y+Y_OFFSET:.3f} {z:.3f} '
        '{'
        'NoGravity:1b,'
        'Invisible:1b,'
        'Invulnerable:1b,'
        f'Rotation:[{yaw:.1f}f],'
        f'Tags:["{TAG}","ghost_{idx}"],'
        f'HandItems:[{held},{{}}],'
        f'ArmorItems:[{",".join(armor)}],'
        f'CustomName:\'{{"text":"{name}"}}\','
        'CustomNameVisible:1b'
        '}'
    )

# ---------------- MAIN ----------------

def init_datapack():
    os.makedirs(FUNC_DIR, exist_ok=True)
    os.makedirs(TAG_DIR, exist_ok=True)

    with open(f"{OUT_DIR}/pack.mcmeta", "w") as f:
        f.write('{ "pack": { "pack_format": 15, "description": "Nostalgia Ghosts" } }')

    # On load: init, ensure any old ghosts are removed, then spawn fresh
    with open(f"{TAG_DIR}/load.json", "w") as f:
        f.write('{ "values": ["ghosts:init", "ghosts:despawn_all", "ghosts:spawn_all"] }')

    # write a small init function that creates the required scoreboards
    with open(f"{FUNC_DIR}/init.mcfunction", "w") as f:
        f.write('scoreboard objectives add ghost_cursor dummy\n')
        f.write('scoreboard objectives add ghost_index dummy\n')
        # use carrot_on_a_stick as the trigger — more reliable per-right-click
        f.write('scoreboard objectives add ghost_use minecraft.used:minecraft.carrot_on_a_stick\n')
        f.write('scoreboard objectives add ghost_last_use dummy\n')
        f.write('scoreboard players set cursor ghost_cursor 0\n')
        # give the nearest player the Ghost Navigator (spyglass)
        f.write("give @p carrot_on_a_stick{display:{Name:'{\"text\":\"Ghost Navigator\"}'}} 1\n")

    # write tick tag so the tick function runs every tick
    with open(f"{TAG_DIR}/tick.json", "w") as f:
        f.write('{ "values": ["ghosts:tick"] }')


def main():
    init_datapack()
    cache = load_cache()

    # write the actual spawn function into spawn_all_actual.mcfunction
    with open(f"{FUNC_DIR}/spawn_all_actual.mcfunction", "w") as out:
        max_idx = 0
        ghosts = []
        files = [f for f in os.listdir(PLAYERDATA_DIR) if f.endswith('.dat')]
        for idx, file in enumerate(files, start=1):

            uuid = file.replace(".dat", "")
            data = nbt.load(os.path.join(PLAYERDATA_DIR, file))

            if "Pos" not in data or "Inventory" not in data:
                continue

            x, y, z = map(float, data["Pos"])
            # Data gets are async
            rot = data.get("Rotation")
            if isinstance(rot, (list, tuple)) and len(rot) > 0 and rot[0] is not None:
                try:
                    yaw = float(rot[0])
                except (TypeError, ValueError):
                    yaw = 0.0
            else:
                yaw = 0.0
            inv = data["Inventory"]
            
            sel_val = data.get("SelectedItemSlot", 0)
            if sel_val is None:
                selected = 0
            else:
                try:
                    selected = int(sel_val)
                except (TypeError, ValueError):
                    selected = 0
                    
            # end of async stuff

            name, textures = uuid_profile(uuid, cache)
            held = get_held(inv, selected)
            armor = get_armor(inv)

            # prepare full SNBT for armor items so we can summon in one command
            leather_map = {
                "feet": "minecraft:leather_boots",
                "legs": "minecraft:leather_leggings",
                "chest": "minecraft:leather_chestplate",
            }

            slots = ["feet", "legs", "chest", "head"]
            armor_snbt = []
            for slot_idx, s in enumerate(slots):
                sn = armor[slot_idx]
                if s == "head":
                    # always equip a player head on the head slot
                    # use player name for SkullOwner
                    owner = name if name else uuid
                    head = ('{id:player_head,Count:1b,tag:{'
                            f'SkullOwner:{owner}'
                            '}}')
                    armor_snbt.append(head)
                else:
                    if sn and sn != "{}":
                        armor_snbt.append(sn)
                    else:
                        leather = leather_map.get(s)
                        armor_snbt.append(f'{{id:"{leather}",Count:1b,tag:{{Damage:0}}}}')

            # held SNBT (hand main) — keep as-is or empty compound
            held_snbt = held if held and held != "{}" else "{}"

            out.write(summon_cmd(x, y, z, yaw, name, held_snbt, armor_snbt, idx) + "\n\n")
            # set a scoreboard value on the summoned armour_stand for ordered selection
            out.write(f'scoreboard players set @e[type=armor_stand,tag=ghost_{idx},limit=1,sort=nearest] ghost_index {idx}\n')
            # record this ghost so teleport function can use literal coords and names
            ghosts.append((idx, float(x), float(y), float(z), name))
            max_idx = idx

        # record how many ghosts we created so teleport function can wrap
        out.write(f'scoreboard players set #ghost_count ghost_index {max_idx}\n')

    # spawn_all.mcfunction: wrapper that only calls the actual spawner when no ghosts exist
    with open(f"{FUNC_DIR}/spawn_all.mcfunction", "w") as wrapper:
        wrapper.write(f'execute unless entity @e[type=armor_stand,tag={TAG}] run function ghosts:spawn_all_actual\n')

    # despawn function to remove all ghosts (useful on shutdown or manual cleanup)
    with open(f"{FUNC_DIR}/despawn_all.mcfunction", "w") as d:
        d.write(f'kill @e[type=armor_stand,tag={TAG}]\n')

    # generate teleport function using the collected ghosts (coords + names)
    write_teleport_function(ghosts)

    save_cache(cache)


def write_teleport_function(ghosts):
    """Generate `teleport_next.mcfunction` which advances the cursor and
    teleports the player to the armour stand tagged with the matching ghost_<n>.
    This function uses explicit conditional branches for each index so it
    doesn't need dynamic selector substitution at runtime.
    """
    os.makedirs(FUNC_DIR, exist_ok=True)
    # per-player teleport function — use @s so multiple players can cycle independently
    with open(f"{FUNC_DIR}/teleport_player.mcfunction", "w") as f:
        # increment this player's cursor
        f.write('scoreboard players add @s ghost_cursor 1\n')
        # wrap if greater than max
        f.write('execute as @s if score @s ghost_cursor > #ghost_count ghost_index run scoreboard players set @s ghost_cursor 1\n')

        # conditional teleport branches (use literal coords and literal names so unloaded entities still have a visible label)
        for (i, x, y, z, name) in ghosts:
            # teleport to the saved coordinates (Y offset applied)
            f.write(f'execute as @s if score @s ghost_cursor matches {i} run tp @s {x:.3f} {y+Y_OFFSET:.3f} {z:.3f}\n')
            # tell the player which ghost they're teleporting to using a literal name (avoids selector returning empty string)
            safe_name = json.dumps(name if name else f"ghost_{i}")
            f.write(f'execute as @s if score @s ghost_cursor matches {i} run tellraw @s [{{"text":"Teleporting to "}},{{"text":{safe_name}}}]\n')

        # update last-use tracker so we don't retrigger
        f.write('scoreboard players operation @s ghost_last_use = @s ghost_use\n')

    # tick handler: call teleport for players who used the bound item
    with open(f"{FUNC_DIR}/tick.mcfunction", "w") as f:
        # only trigger teleport when player is holding the named trigger item to avoid false positives
        f.write('execute as @a[nbt={SelectedItem:{id:"minecraft:carrot_on_a_stick",tag:{display:{Name:\'{"text":"Ghost Navigator"}\'}}}}] if score @s ghost_use > @s ghost_last_use run function ghosts:teleport_player\n')

    # convenience manual functions so players can bind a key or run command themselves
    with open(f"{FUNC_DIR}/teleport_next.mcfunction", "w") as f:
        f.write('function ghosts:teleport_player\n')

    with open(f"{FUNC_DIR}/teleport_prev.mcfunction", "w") as f:
        # decrement this player's cursor, wrap if < 1, then teleport
        f.write('scoreboard players remove @s ghost_cursor 1\n')
        f.write('execute as @s if score @s ghost_cursor < 1 ghost_index run scoreboard players operation @s ghost_cursor = #ghost_count ghost_index\n')
        f.write('function ghosts:teleport_player\n')


if __name__ == "__main__":
    main()
