#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request
import math, random
from collections import deque

app = Flask(__name__)

# ==========================
# KONSTANTOK
# ==========================
DEVICE_INSTALL_COST = 200         # Eszköz telepítés ára
CABLE_COST_PER_KM = 100           # Kábel költség (egység/km)
REPAIR_DEVICE_COST = 100          # Eszköz javítás ára

# Kábel szintjének kapacitása (Mbit/s)
def cable_capacity(level):
    mapping = {
        1: 10,       # 10 Mbit/s
        2: 100,      # 100 Mbit/s
        3: 1000,     # 1 Gbit/s = 1000 Mbit/s
        4: 10000,    # 10 Gbit/s
        5: 100000    # 100 Gbit/s
    }
    return mapping.get(level, 10)

# Haversine képlet két pont távolságának kiszámításához (km-ben)
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Föld sugara km-ben
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ==========================
# JÁTÉK ÁLLAPOTA
# ==========================
def init_game_state():
    return {
    'money': 2000,
    'buildings': {
        # Statikus épületek 47.51803138137886, 19.055572371807745
        'B1': {'name': 'Buda - Palota', 'lat': 47.49696826785844, 'lng': 19.038296031130105, 'region': 'Buda',
               'device_installed': False, 'device_status': 'NONE', 'demand': 100},
        'B2': {'name': 'Parlament', 'lat': 47.5070, 'lng': 19.0450, 'region': 'Buda',
               'device_installed': False, 'device_status': 'NONE', 'demand': 200},
        'B3': {'name': 'Clark Ádám tér', 'lat': 47.4979, 'lng': 19.0402, 'region': 'Pest',
               'device_installed': False, 'device_status': 'NONE', 'demand': 50},
        'B4': {'name': 'Aladár utca', 'lat': 47.4900, 'lng': 19.0350, 'region': 'Pest',
               'device_installed': False, 'device_status': 'NONE', 'demand': 300},
        # Internet kijárat – ez egy speciális node, mindig működő
        'EXIT': {'name': 'Internet Kijárat - Budapest, Victor Hugo u. 18, 1132',
                 'lat': 47.51803138137886, 'lng': 19.055572371807745, 'region': 'Pest',
                 'device_installed': True, 'device_status': 'OK', 'is_exit': True},
        # Kezdetben az internet kijárat körül 3 db 50 Mbit/s-es épület
        'I1': {'name': 'Internet Épület 1', 'lat': 47.5145, 'lng': 19.055572371807745, 'region': 'Pest',
               'device_installed': False, 'device_status': 'NONE', 'demand': 50},
        'I2': {'name': 'Internet Épület 2', 'lat': 47.5155, 'lng': 19.055432371807745, 'region': 'Pest',
               'device_installed': False, 'device_status': 'NONE', 'demand': 50},
        'I3': {'name': 'Internet Épület 3', 'lat': 47.5250, 'lng': 19.059102, 'region': 'Pest',
               'device_installed': False, 'device_status': 'NONE', 'demand': 50}
    },
    'bridges': {
        'H1': {'name': 'Széchenyi Lánchíd', 'lat': 47.4980, 'lng': 19.0450},
        'H2': {'name': 'Margit híd', 'lat': 47.4990, 'lng': 19.0600}
    },
    'cables': {
        # Ide kerülnek majd a bekötött kábelek; a kábel objektum tartalmazza:
        # 'from', 'to', 'level', 'status', 'distance', 'cost'
    },
    'next_cable_id': 1,
    'next_building_id': 7  # A statikus épületek után az új épületek számozása
}

# Inicializáljuk a játékállapotot
game_state = init_game_state()
# ==========================
# SEGÉDFÜGGVÉNY: Útvonal keresés az EXIT-hez (BFS az OK kábelekkel)
# ==========================
def find_path_to_exit(start):
    if start == "EXIT":
        return ([], 0)
    queue = deque()
    queue.append((start, [], 0))
    visited = set([start])
    while queue:
        current, path, dist = queue.popleft()
        for cable_id, cable in game_state['cables'].items():
            if cable['status'] != "OK":
                continue
            if cable['from'] == current:
                neighbor = cable['to']
            elif cable['to'] == current:
                neighbor = cable['from']
            else:
                continue
            if neighbor in visited:
                continue
            new_path = path + [cable_id]
            new_dist = dist + cable['distance']
            if neighbor == "EXIT":
                return (new_path, new_dist)
            visited.add(neighbor)
            queue.append((neighbor, new_path, new_dist))
    return (None, None)

# ==========================
# ENDPOINTOK
# ==========================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/state')
def state():
    return jsonify(game_state)
    
# Új endpoint: /reset
@app.route('/reset', methods=['POST'])
def reset_game():
    global game_state
    game_state = init_game_state()
    return jsonify({'success': True, 'message': 'A játék vissza lett állítva az eredeti állapotra.'})

@app.route('/install/<building_id>', methods=['POST'])
def install_device(building_id):
    if building_id not in game_state['buildings']:
        return jsonify({'success': False, 'message': 'Ismeretlen épület.'})
    building = game_state['buildings'][building_id]
    if building.get('is_exit', False):
        return jsonify({'success': False, 'message': 'Ez a node nem telepíthető/javítandó.'})
    if building['device_installed']:
        return jsonify({'success': False, 'message': 'Eszköz már telepítve.'})
    if game_state['money'] < DEVICE_INSTALL_COST:
        return jsonify({'success': False, 'message': 'Nincs elég pénz az eszköz telepítéséhez.'})
    game_state['money'] -= DEVICE_INSTALL_COST
    building['device_installed'] = True
    building['device_status'] = 'OK'
    return jsonify({'success': True, 'message': f"Eszköz telepítve: {building['name']} (Költség: {DEVICE_INSTALL_COST})"})

@app.route('/repair_device/<building_id>', methods=['POST'])
def repair_device(building_id):
    if building_id not in game_state['buildings']:
        return jsonify({'success': False, 'message': 'Ismeretlen épület.'})
    building = game_state['buildings'][building_id]
    if building.get('is_exit', False):
        return jsonify({'success': False, 'message': 'Ez a node nem javítható.'})
    if building['device_status'] != 'FAULT':
        return jsonify({'success': False, 'message': 'Az eszköz nem hibás.'})
    if game_state['money'] < REPAIR_DEVICE_COST:
        return jsonify({'success': False, 'message': 'Nincs elég pénz az eszköz javításához.'})
    game_state['money'] -= REPAIR_DEVICE_COST
    building['device_status'] = 'OK'
    return jsonify({'success': True, 'message': f"Eszköz javítva: {building['name']} (Költség: {REPAIR_DEVICE_COST})"})

@app.route('/repair_cable/<cable_id>', methods=['POST'])
def repair_cable(cable_id):
    if cable_id not in game_state['cables']:
        return jsonify({'success': False, 'message': 'Ismeretlen kábel.'})
    cable = game_state['cables'][cable_id]
    if cable['status'] == "OK":
        return jsonify({'success': False, 'message': 'A kábel nem hibás.'})
    cost = cable['level'] * 300  # Például a kábel szintjétől függő javítási költség
    if game_state['money'] < cost:
        return jsonify({'success': False, 'message': f'Nincs elég pénz a kábel javításához (szükséges: {cost}).'})
    game_state['money'] -= cost
    cable['status'] = "OK"
    return jsonify({'success': True, 'message': f"A kábel {cable_id} sikeresen javítva (Költség: {cost})."})

@app.route('/connect', methods=['POST'])
def connect_devices():
    data = request.get_json()
    from_id = data.get('from')
    to_id = data.get('to')
    # Várjuk az opcionális cable level paramétert (1-től 5-ig), alapértelmezetten 1
    cable_level = data.get('level', 1)
    try:
        cable_level = int(cable_level)
    except:
        cable_level = 1
    if cable_level < 1 or cable_level > 5:
        cable_level = 1

    if from_id not in game_state['buildings'] or to_id not in game_state['buildings']:
        return jsonify({'success': False, 'message': 'Érvénytelen épület azonosító.'})
    b1 = game_state['buildings'][from_id]
    b2 = game_state['buildings'][to_id]
    if not b1.get('is_exit', False):
        if not (b1['device_installed'] and b1['device_status'] == 'OK'):
            return jsonify({'success': False, 'message': 'Az első épületnél működő eszköz szükséges.'})
    if not b2.get('is_exit', False):
        if not (b2['device_installed'] and b2['device_status'] == 'OK'):
            return jsonify({'success': False, 'message': 'A második épületnél működő eszköz szükséges.'})
    # Távolság számítása
    if b1['region'] == b2['region']:
        distance = haversine(b1['lat'], b1['lng'], b2['lat'], b2['lng'])
    else:
        if b1.get('is_exit', False) or b2.get('is_exit', False):
            distance = haversine(b1['lat'], b1['lng'], b2['lat'], b2['lng'])
        else:
            best_distance = None
            for bridge in game_state['bridges'].values():
                d = haversine(b1['lat'], b1['lng'], bridge['lat'], bridge['lng']) + \
                    haversine(bridge['lat'], bridge['lng'], b2['lat'], b2['lng'])
                if best_distance is None or d < best_distance:
                    best_distance = d
            if best_distance is None:
                return jsonify({'success': False, 'message': 'Nincs elérhető híd a két régió között.'})
            distance = best_distance
    
    # Számoljuk ki a kábel költségét úgy, hogy az a választott szinttel arányos legyen.
    base_cost = int(round(distance * CABLE_COST_PER_KM))
    cable_cost = base_cost * cable_level

    if game_state['money'] < cable_cost:
        return jsonify({'success': False, 'message': f'Nincs elég pénz a kábel telepítéséhez (szükséges: {cable_cost}).'})
    game_state['money'] -= cable_cost
    cable_id = f"C{game_state['next_cable_id']}"
    game_state['next_cable_id'] += 1
    # A kábel objektumhoz eltároljuk a kiválasztott szintet és a költséget is.
    game_state['cables'][cable_id] = {
        'from': from_id,
        'to': to_id,
        'level': cable_level,
        'status': 'OK',
        'distance': round(distance, 2),
        'cost': cable_cost
    }
    return jsonify({'success': True, 'message': f"Kábel {cable_id} létrehozva (távolság: {round(distance,2)} km, szint: {cable_level}, költség: {cable_cost}).", 'cable_id': cable_id})

@app.route('/upgrade/<cable_id>', methods=['POST'])
def upgrade_cable(cable_id):
    if cable_id not in game_state['cables']:
        return jsonify({'success': False, 'message': 'Ismeretlen kábel.'})
    cable = game_state['cables'][cable_id]
    if cable['level'] >= 5:
        return jsonify({'success': False, 'message': 'A kábel már a maximum szinten van.'})
    cost = cable['level'] * 500
    if game_state['money'] < cost:
        return jsonify({'success': False, 'message': 'Nincs elég pénz az upgrade-hez.'})
    game_state['money'] -= cost
    cable['level'] += 1
    return jsonify({'success': True, 'message': f"Kábel {cable_id} upgrade-elése sikeres. Új szint: {cable['level']} (Költség: {cost})."})

# Új endpoint: kábel törlése refundtal
@app.route('/delete_cable/<cable_id>', methods=['POST'])
def delete_cable(cable_id):
    if cable_id not in game_state['cables']:
        return jsonify({'success': False, 'message': 'Ismeretlen kábel.'})
    cable = game_state['cables'][cable_id]
    # Töröljük a kábelt, és refundolunk a telepítés költségének 1/3-át
    refund = int(round(cable.get('cost', 0) / 3))
    game_state['money'] += refund
    del game_state['cables'][cable_id]
    return jsonify({'success': True, 'message': f"Kábel {cable_id} törölve. Visszakaptál: {refund} egységet."})

@app.route('/simulate', methods=['POST'])
def simulate():
    """
    Szimulációs tick:
      - Minden nem EXIT épületből, amelynél telepített és működő eszköz van,
        megkeressük az utat az internet kijárathoz.
      - Az egyes épületek forgalmát (a saját demand értéküket) hozzáadjuk az útvonalon lévő kábelekre.
      - Ha egy kábelre érkező forgalom meghaladja a kábel kapacitását,
        a kábel FAULT állapotba kerül.
      - A kábelek adatai (current_load, capacity) frissülnek.
      - A bevétel a kijárathoz eljutó internet forgalom összegétől függ, 
        de mostantól a távolságot is figyelembe vesszük: minél messzebbről érkezik a sebesség, annál többet kap a rendszer.
    """
    cable_load = {}   # cable_id -> összforgalom (Mbit/s)
    cable_users = {}  # cable_id -> azon épületek listája, amelyek forgalmát a kábelen keresztül küldik

    # Első lépés: forgalom összegyűjtése az egyes kábellel rendelkező útvonalakra
    for b_id, building in game_state['buildings'].items():
        if b_id == "EXIT":
            continue
        if not (building['device_installed'] and building['device_status'] == 'OK'):
            continue
        demand = building.get('demand', 100)
        path, route_distance = find_path_to_exit(b_id)
        if path is None:
            continue
        for cable_id in path:
            cable_load[cable_id] = cable_load.get(cable_id, 0) + demand
            cable_users.setdefault(cable_id, []).append(b_id)

    overloaded_cables = []
    for cable_id, load in cable_load.items():
        cable = game_state['cables'][cable_id]
        if load > cable_capacity(cable['level']):
            cable['status'] = 'FAULT'
            overloaded_cables.append(cable_id)
            # Csak a kábel hibásodik meg, az épületek eszköze maradnak működőképesek.
    
    # Frissítjük a kábelek adatait a frontend számára
    for cable_id, cable in game_state['cables'].items():
        cable['current_load'] = cable_load.get(cable_id, 0)
        cable['capacity'] = cable_capacity(cable['level'])
    
    # Bevétel számítása: minden olyan épület, amelynek sikeresen van útja az EXIT-hez,
    # bevételét a demand és az útvonal hosszának szorzataként számoljuk.
    total_internet_traffic = 0
    revenue = 0
    for b_id, building in game_state['buildings'].items():
        if b_id == "EXIT":
            continue
        if building['device_installed'] and building['device_status'] == 'OK':
            path, route_distance = find_path_to_exit(b_id)
            if path is not None:
                total_internet_traffic += building.get('demand', 100)
                # Például: az épület bevétele = demand * route_distance (km-ben)
                revenue += building.get('demand', 100) * route_distance
    game_state['money'] += revenue

    return jsonify({
        'success': True,
        'message': f"Szimuláció lefutott. Bevétel: {revenue} egység. (Internet forgalom: {total_internet_traffic} Mbit/s)",
        'overloaded': overloaded_cables
    })


@app.route('/add_building', methods=['POST'])
def add_building():
    # Új épület létrehozása 60 másodpercenként
    next_id = game_state.get('next_building_id', 7)
    building_id = "B" + str(next_id)
    game_state['next_building_id'] = next_id + 1
    lat = round(random.uniform(47.48, 47.52), 4)
    lng = round(random.uniform(19.03, 19.07), 4)
    demand = random.choice([50, 100, 200, 300, 500])
    region = random.choice(["Buda", "Pest"])
    name = "Új Épület " + building_id
    game_state['buildings'][building_id] = {
        'name': name,
        'lat': lat,
        'lng': lng,
        'region': region,
        'device_installed': False,
        'device_status': 'NONE',
        'demand': demand
    }
    return jsonify({'success': True, 'message': f"Új épület hozzáadva: {name}, demand: {demand} Mbit/s.", 'building_id': building_id})

if __name__ == '__main__':
    import webbrowser
    port = 5000
    url = f'http://127.0.0.1:{port}'
    webbrowser.open(url)  # Automatikusan megnyitja az alapértelmezett böngészőben az URL-t
    app.run(debug=True, port=port)

