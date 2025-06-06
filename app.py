from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from datetime import datetime, timedelta
import re

app = Flask(__name__)
app.secret_key = 'supersecreto'
DATABASE = 'calendario_notas.db'

# Helper functions for dd/mm/yyyy

def to_ddmmyyyy(date_obj):
    return date_obj.strftime('%d/%m/%Y')

def from_ddmmyyyy(date_str):
    return datetime.strptime(date_str, '%d/%m/%Y')

def to_ddmmyyyy_hhmm(date_obj):
    return date_obj.strftime('%d/%m/%Y %H:%M')

def from_ddmmyyyy_hhmm(date_str):
    return datetime.strptime(date_str, '%d/%m/%Y %H:%M')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return redirect(url_for('mis_notas'))

@app.route('/agregar-nota', methods=['GET', 'POST'])
def agregar_nota():
    if request.method == 'POST':
        titulo = request.form['titulo']
        contenido = request.form['contenido']
        categoria = request.form['categoria']
        fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db()
        conn.execute('INSERT INTO notas (titulo, contenido, categoria, fecha_creacion, fecha_edicion, utilizada) VALUES (?, ?, ?, ?, ?, ?)',
                     (titulo, contenido, categoria, fecha, fecha, 'no utilizada'))
        conn.commit()
        conn.close()
        return redirect(url_for('mis_notas'))
    conn = get_db()
    categorias = conn.execute('SELECT DISTINCT categoria FROM notas').fetchall()
    conn.close()
    categorias = [row['categoria'] for row in categorias]
    return render_template('agregar_nota.html', categorias=categorias)

@app.route('/mis-notas')
def mis_notas():
    conn = get_db()
    notas = conn.execute('SELECT * FROM notas ORDER BY fecha_creacion DESC').fetchall()
    conn.close()
    return render_template('mis_notas.html', notas=notas)

@app.route('/agregar-evento', methods=['GET', 'POST'])
def agregar_evento():
    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        categoria = request.form['categoria']
        fecha_inicio = parse_to_iso(request.form['fecha_inicio'])
        fecha_final = parse_to_iso(request.form['fecha_final'])
        repeticion = request.form['repeticion']
        repeticion_detalle = request.form.get('repeticion_detalle', '')
        estado = request.form['estado']
        fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db()
        conn.execute('''INSERT INTO eventos (titulo, descripcion, categoria, fecha_inicio, fecha_final, fecha_creacion, fecha_edicion, repeticion, repeticion_detalle, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (titulo, descripcion, categoria, fecha_inicio, fecha_final, fecha, fecha, repeticion, repeticion_detalle, estado))
        conn.commit()
        conn.close()
        # flash('Evento agregado exitosamente.')  # Eliminado para no mostrar mensaje
        return redirect(url_for('calendario'))
    conn = get_db()
    categorias = conn.execute('SELECT DISTINCT categoria FROM eventos').fetchall()
    conn.close()
    categorias = [row['categoria'] for row in categorias]
    return render_template('agregar_evento.html', categorias=categorias)

@app.route('/calendario')
def calendario():
    conn = get_db()
    eventos = conn.execute('SELECT * FROM eventos').fetchall()
    conn.close()
    return render_template('calendario.html', eventos=eventos)

def normalize_fecha(fecha):
    if not fecha:
        return ''
    if isinstance(fecha, str):
        # If already correct
        if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$', fecha):
            return fecha
        # If with seconds
        if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', fecha):
            return fecha[:16]
        # Try to parse
        try:
            d = datetime.fromisoformat(fecha)
            return d.strftime('%Y-%m-%dT%H:%M')
        except Exception:
            return fecha[:16]
    return fecha

@app.route('/api/eventos')
def api_eventos():
    # Get start and end from query parameters (may be None)
    start_param = request.args.get('start')
    end_param = request.args.get('end')

    conn = get_db()
    eventos = conn.execute('SELECT * FROM eventos').fetchall()
    # Load all occurrence states
    ocurrencias = conn.execute('SELECT * FROM evento_ocurrencias').fetchall()
    conn.close()
    ocurrencias_dict = {
        (o['evento_id'], normalize_fecha(o['fecha_inicio'])): o['estado']
        for o in ocurrencias
    }
    print('DEBUG: ocurrencias_dict keys:', list(ocurrencias_dict.keys()))
    eventos_json = []
    for e in eventos:
        rep = e['repeticion']
        try:
            start = to_iso_with_T(e['fecha_inicio'])
            end = to_iso_with_T(e['fecha_final'])
        except Exception as ex:
            print(f"Exception parsing event {e['id']}: {ex}")
            continue  # skip malformed events

        print(f"Processing event {e['id']} ({e['titulo']}), rep: {rep}, start: {start}, end: {end}")

        # Limit expansion to 1 year max or until filter_end if provided
        if start_param and end_param:
            try:
                filter_end = datetime.fromisoformat(end_param)
                if filter_end.tzinfo is not None:
                    filter_end = filter_end.replace(tzinfo=None)
                max_end = min(filter_end, start + timedelta(days=365))
            except Exception:
                max_end = start + timedelta(days=365)
        else:
            max_end = start + timedelta(days=365)
        occurrences = []
        if rep == 'ninguna':
            lookup_key = (e['id'], start.strftime('%Y-%m-%dT%H:%M'))
            estado = ocurrencias_dict.get(lookup_key, e['estado'])
            occurrences.append({
                'id': e['id'],
                'title': e['titulo'],
                'start': start.strftime('%Y-%m-%dT%H:%M'),
                'end': end.strftime('%Y-%m-%dT%H:%M'),
                'descripcion': e['descripcion'],
                'categoria': e['categoria'],
                'repeticion': e['repeticion'],
                'repeticion_detalle': e['repeticion_detalle'],
                'estado': estado
            })
        elif rep == 'diario':
            current = start
            while current <= max_end:
                lookup_key = (e['id'], current.strftime('%Y-%m-%dT%H:%M'))
                estado = ocurrencias_dict.get(lookup_key, e['estado'])
                print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
                if estado == 'omitido':
                    current += timedelta(days=1)
                    continue
                occurrences.append({
                    'id': f"{e['id']}_d_{current.strftime('%Y%m%d')}",
                    'title': e['titulo'],
                    'start': current.strftime('%Y-%m-%dT%H:%M'),
                    'end': (current + (end - start)).strftime('%Y-%m-%dT%H:%M'),
                    'descripcion': e['descripcion'],
                    'categoria': e['categoria'],
                    'repeticion': e['repeticion'],
                    'repeticion_detalle': e['repeticion_detalle'],
                    'estado': estado
                })
                current += timedelta(days=1)
        elif rep == 'semanal':
            current = start
            while current <= max_end:
                lookup_key = (e['id'], current.strftime('%Y-%m-%dT%H:%M'))
                estado = ocurrencias_dict.get(lookup_key, e['estado'])
                print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
                if estado == 'omitido':
                    current += timedelta(weeks=1)
                    continue
                occurrences.append({
                    'id': f"{e['id']}_w_{current.strftime('%Y%m%d')}",
                    'title': e['titulo'],
                    'start': current.strftime('%Y-%m-%dT%H:%M'),
                    'end': (current + (end - start)).strftime('%Y-%m-%dT%H:%M'),
                    'descripcion': e['descripcion'],
                    'categoria': e['categoria'],
                    'repeticion': e['repeticion'],
                    'repeticion_detalle': e['repeticion_detalle'],
                    'estado': estado
                })
                current += timedelta(weeks=1)
        elif rep == 'mensual':
            current = start
            while current <= max_end:
                lookup_key = (e['id'], current.strftime('%Y-%m-%dT%H:%M'))
                estado = ocurrencias_dict.get(lookup_key, e['estado'])
                print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
                if estado == 'omitido':
                    # Move to next month, same day
                    year = current.year + (current.month // 12)
                    month = (current.month % 12) + 1
                    day = current.day
                    try:
                        current = current.replace(year=year, month=month)
                    except ValueError:
                        while True:
                            day -= 1
                            try:
                                current = current.replace(year=year, month=month, day=day)
                                break
                            except ValueError:
                                continue
                    continue
                occurrences.append({
                    'id': f"{e['id']}_m_{current.strftime('%Y%m')}",
                    'title': e['titulo'],
                    'start': current.strftime('%Y-%m-%dT%H:%M'),
                    'end': (current + (end - start)).strftime('%Y-%m-%dT%H:%M'),
                    'descripcion': e['descripcion'],
                    'categoria': e['categoria'],
                    'repeticion': e['repeticion'],
                    'repeticion_detalle': e['repeticion_detalle'],
                    'estado': estado
                })
                # Move to next month, same day
                year = current.year + (current.month // 12)
                month = (current.month % 12) + 1
                day = current.day
                try:
                    current = current.replace(year=year, month=month)
                except ValueError:
                    while True:
                        day -= 1
                        try:
                            current = current.replace(year=year, month=month, day=day)
                            break
                        except ValueError:
                            continue
        elif rep == 'anual':
            current = start
            while current <= max_end:
                lookup_key = (e['id'], current.strftime('%Y-%m-%dT%H:%M'))
                estado = ocurrencias_dict.get(lookup_key, e['estado'])
                print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
                if estado == 'omitido':
                    try:
                        current = current.replace(year=current.year + 1)
                    except ValueError:
                        current = current.replace(month=2, day=28, year=current.year + 1)
                    continue
                occurrences.append({
                    'id': f"{e['id']}_y_{current.strftime('%Y')}",
                    'title': e['titulo'],
                    'start': current.strftime('%Y-%m-%dT%H:%M'),
                    'end': (current + (end - start)).strftime('%Y-%m-%dT%H:%M'),
                    'descripcion': e['descripcion'],
                    'categoria': e['categoria'],
                    'repeticion': e['repeticion'],
                    'repeticion_detalle': e['repeticion_detalle'],
                    'estado': estado
                })
                try:
                    current = current.replace(year=current.year + 1)
                except ValueError:
                    current = current.replace(month=2, day=28, year=current.year + 1)
        elif rep == 'diario_laboral':
            current = start
            while current <= max_end:
                if current.weekday() < 5:  # Monday=0, ..., Friday=4
                    lookup_key = (e['id'], current.strftime('%Y-%m-%dT%H:%M'))
                    estado = ocurrencias_dict.get(lookup_key, e['estado'])
                    print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
                    if estado == 'omitido':
                        current += timedelta(days=1)
                        continue
                    occurrences.append({
                        'id': f"{e['id']}_dl_{current.strftime('%Y%m%d')}",
                        'title': e['titulo'],
                        'start': current.strftime('%Y-%m-%dT%H:%M'),
                        'end': (current + (end - start)).strftime('%Y-%m-%dT%H:%M'),
                        'descripcion': e['descripcion'],
                        'categoria': e['categoria'],
                        'repeticion': e['repeticion'],
                        'repeticion_detalle': e['repeticion_detalle'],
                        'estado': estado
                    })
                current += timedelta(days=1)
        elif rep == 'personalizado':
            # Support both 'Repite N ...' (repeat N times), 'Repite cada N ...' (repeat every N units), and 'El N [día] de cada mes'
            detalle = e['repeticion_detalle'] or ''
            match_repite_n = re.match(r'Repite\s*(\d+)\s*(d[ií]as|semanas|meses|a[nñ]os)', detalle, re.IGNORECASE)
            match_repite_cada_n = re.match(r'Repite cada\s*(\d+)\s*(d[ií]as|semanas|meses|a[nñ]os)', detalle, re.IGNORECASE)
            match_el_n_dia_mes = re.match(r'El\s+(primer|primero|segundo|tercero|cuarto|quinto|último)\s+(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+de cada mes', detalle, re.IGNORECASE)
            if match_repite_n:
                count = int(match_repite_n.group(1))
                unit = match_repite_n.group(2).lower()
                current = start
                for i in range(count):
                    lookup_key = (e['id'], current.strftime('%Y-%m-%dT%H:%M'))
                    estado = ocurrencias_dict.get(lookup_key, e['estado'])
                    print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
                    if estado == 'omitido':
                        if 'semana' in unit:
                            current += timedelta(weeks=1)
                        elif 'día' in unit or 'dia' in unit:
                            current += timedelta(days=1)
                        elif 'mes' in unit:
                            month = current.month
                            year = current.year
                            month += 1
                            if month > 12:
                                month = 1
                                year += 1
                            day = min(current.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
                            try:
                                current = current.replace(year=year, month=month, day=day)
                            except Exception:
                                current = current.replace(year=year, month=month, day=1)
                        elif 'año' in unit or 'ano' in unit:
                            try:
                                current = current.replace(year=current.year + 1)
                            except Exception:
                                current = current.replace(month=2, day=28, year=current.year + 1)
                        continue
                    occurrences.append({
                        'id': f"{e['id']}_p_{current.strftime('%Y%m%d')}",
                        'title': e['titulo'],
                        'start': current.strftime('%Y-%m-%dT%H:%M'),
                        'end': (current + (end - start)).strftime('%Y-%m-%dT%H:%M'),
                        'descripcion': e['descripcion'],
                        'categoria': e['categoria'],
                        'repeticion': e['repeticion'],
                        'repeticion_detalle': e['repeticion_detalle'],
                        'estado': estado
                    })
                    if 'semana' in unit:
                        current += timedelta(weeks=1)
                    elif 'día' in unit or 'dia' in unit:
                        current += timedelta(days=1)
                    elif 'mes' in unit:
                        month = current.month
                        year = current.year
                        month += 1
                        if month > 12:
                            month = 1
                            year += 1
                        day = min(current.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
                        try:
                            current = current.replace(year=year, month=month, day=day)
                        except Exception:
                            current = current.replace(year=year, month=month, day=1)
                    elif 'año' in unit or 'ano' in unit:
                        try:
                            current = current.replace(year=current.year + 1)
                        except Exception:
                            current = current.replace(month=2, day=28, year=current.year + 1)
            elif match_repite_cada_n:
                interval = int(match_repite_cada_n.group(1))
                unit = match_repite_cada_n.group(2).lower()
                current = start
                while current <= max_end:
                    lookup_key = (e['id'], current.strftime('%Y-%m-%dT%H:%M'))
                    estado = ocurrencias_dict.get(lookup_key, e['estado'])
                    print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
                    if estado == 'omitido':
                        if 'semana' in unit:
                            current += timedelta(weeks=interval)
                        elif 'día' in unit or 'dia' in unit:
                            current += timedelta(days=interval)
                        elif 'mes' in unit:
                            month = current.month
                            year = current.year
                            month += interval
                            while month > 12:
                                month -= 12
                                year += 1
                            day = min(current.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
                            try:
                                current = current.replace(year=year, month=month, day=day)
                            except Exception:
                                current = current.replace(year=year, month=month, day=1)
                        elif 'año' in unit or 'ano' in unit:
                            try:
                                current = current.replace(year=current.year + interval)
                            except Exception:
                                current = current.replace(month=2, day=28, year=current.year + interval)
                        continue
                    occurrences.append({
                        'id': f"{e['id']}_pc_{current.strftime('%Y%m%d')}",
                        'title': e['titulo'],
                        'start': current.strftime('%Y-%m-%dT%H:%M'),
                        'end': (current + (end - start)).strftime('%Y-%m-%dT%H:%M'),
                        'descripcion': e['descripcion'],
                        'categoria': e['categoria'],
                        'repeticion': e['repeticion'],
                        'repeticion_detalle': e['repeticion_detalle'],
                        'estado': estado
                    })
                    if 'semana' in unit:
                        current += timedelta(weeks=interval)
                    elif 'día' in unit or 'dia' in unit:
                        current += timedelta(days=interval)
                    elif 'mes' in unit:
                        month = current.month
                        year = current.year
                        month += interval
                        while month > 12:
                            month -= 12
                            year += 1
                        day = min(current.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
                        try:
                            current = current.replace(year=year, month=month, day=day)
                        except Exception:
                            current = current.replace(year=year, month=month, day=1)
                    elif 'año' in unit or 'ano' in unit:
                        try:
                            current = current.replace(year=current.year + interval)
                        except Exception:
                            current = current.replace(month=2, day=28, year=current.year + interval)
            elif match_el_n_dia_mes:
                # Parse ordinal and weekday
                ordinal_map = {
                    'primer': 1,
                    'primero': 1,
                    'segundo': 2,
                    'tercero': 3,
                    'cuarto': 4,
                    'quinto': 5,
                    'último': -1
                }
                weekday_map = {
                    'lunes': 0,
                    'martes': 1,
                    'miércoles': 2,
                    'jueves': 3,
                    'viernes': 4,
                    'sábado': 5,
                    'domingo': 6
                }
                ordinal = ordinal_map[match_el_n_dia_mes.group(1).lower()]
                weekday = weekday_map[match_el_n_dia_mes.group(2).lower()]
                # Start from the month of 'start', go up to max_end
                current_month = start.replace(day=1)
                while current_month <= max_end:
                    # Find all days in this month that match the weekday
                    days = []
                    d = current_month
                    while d.month == current_month.month:
                        if d.weekday() == weekday:
                            days.append(d)
                        d += timedelta(days=1)
                    if ordinal > 0:
                        if len(days) >= ordinal:
                            occ_day = days[ordinal-1]
                        else:
                            occ_day = None
                    else:  # último
                        occ_day = days[-1] if days else None
                    if occ_day:
                        lookup_key = (e['id'], occ_day.strftime('%Y-%m-%dT%H:%M'))
                        estado = ocurrencias_dict.get(lookup_key, e['estado'])
                        print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
                        if estado == 'omitido':
                            continue
                        occurrences.append({
                            'id': f"{e['id']}_em_{occ_day.strftime('%Y%m%d')}",
                            'title': e['titulo'],
                            'start': occ_day.strftime('%Y-%m-%dT%H:%M'),
                            'end': (occ_day + (end - start)).strftime('%Y-%m-%dT%H:%M'),
                            'descripcion': e['descripcion'],
                            'categoria': e['categoria'],
                            'repeticion': e['repeticion'],
                            'repeticion_detalle': e['repeticion_detalle'],
                            'estado': estado
                        })
                    # Move to next month
                    year = current_month.year + (current_month.month // 12)
                    month = (current_month.month % 12) + 1
                    try:
                        current_month = current_month.replace(year=year, month=month, day=1)
                    except Exception:
                        # Handle edge cases
                        current_month = current_month.replace(year=year, month=month, day=1)
            else:
                # fallback: single occurrence
                lookup_key = (e['id'], start.strftime('%Y-%m-%dT%H:%M'))
                estado = ocurrencias_dict.get(lookup_key, e['estado'])
                print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
                if estado == 'omitido':
                    continue
                occurrences.append({
                    'id': e['id'],
                    'title': e['titulo'],
                    'start': start.strftime('%Y-%m-%dT%H:%M'),
                    'end': end.strftime('%Y-%m-%dT%H:%M'),
                    'descripcion': e['descripcion'],
                    'categoria': e['categoria'],
                    'repeticion': e['repeticion'],
                    'repeticion_detalle': e['repeticion_detalle'],
                    'estado': estado
                })
        else:
            lookup_key = (e['id'], start.strftime('%Y-%m-%dT%H:%M'))
            estado = ocurrencias_dict.get(lookup_key, e['estado'])
            print(f'DEBUG: Looking up {lookup_key}, found estado: {estado}')
            if estado == 'omitido':
                continue
            occurrences.append({
                'id': e['id'],
                'title': e['titulo'],
                'start': start.strftime('%Y-%m-%dT%H:%M'),
                'end': end.strftime('%Y-%m-%dT%H:%M'),
                'descripcion': e['descripcion'],
                'categoria': e['categoria'],
                'repeticion': e['repeticion'],
                'repeticion_detalle': e['repeticion_detalle'],
                'estado': estado
            })

        # Now filter occurrences by start_param/end_param if provided
        if start_param and end_param:
            try:
                try:
                    filter_start = datetime.fromisoformat(start_param)
                except Exception:
                    filter_start = datetime.fromisoformat(start_param[:16])
                try:
                    filter_end = datetime.fromisoformat(end_param)
                except Exception:
                    filter_end = datetime.fromisoformat(end_param[:16])
                # Make filter_start and filter_end offset-naive for comparison
                if filter_start.tzinfo is not None:
                    filter_start = filter_start.replace(tzinfo=None)
                if filter_end.tzinfo is not None:
                    filter_end = filter_end.replace(tzinfo=None)
                print(f"Filtering occurrences between {filter_start} and {filter_end}")
                new_occurrences = []
                for occ in occurrences:
                    occ_start = datetime.strptime(occ['start'], '%Y-%m-%dT%H:%M')
                    occ_end = datetime.strptime(occ['end'], '%Y-%m-%dT%H:%M')
                    if not (occ_end < filter_start or occ_start > filter_end):
                        new_occurrences.append(occ)
                    else:
                        print(f"Filtered out occurrence: {occ['start']} - {occ['end']}")
                occurrences = new_occurrences
            except Exception as ex:
                print(f"Exception in filtering: {ex}")
                pass

        eventos_json.extend(occurrences)
    # --- Add extra occurrences from evento_ocurrencias not generated above ---
    generated_keys = set((str(occ['id']), occ['start']) for occ in eventos_json)
    for o in ocurrencias:
        if o['estado'] == 'omitido':
            continue
        # Normalize fecha_inicio for comparison
        fecha_inicio_norm = normalize_fecha(o['fecha_inicio'])
        # Check if this occurrence is already in eventos_json
        already_included = any(
            str(occ['id']).startswith(str(o['evento_id'])) and occ['start'] == fecha_inicio_norm
            for occ in eventos_json
        )
        if not already_included:
            # Get the event info
            e = next((ev for ev in eventos if ev['id'] == o['evento_id']), None)
            if not e:
                continue
            eventos_json.append({
                'id': f"{e['id']}_moved_{fecha_inicio_norm.replace('-','').replace(':','').replace('T','')}",
                'title': e['titulo'],
                'start': fecha_inicio_norm,
                'end': normalize_fecha(o['fecha_final']),
                'descripcion': e['descripcion'],
                'categoria': e['categoria'],
                'repeticion': e['repeticion'],
                'repeticion_detalle': e['repeticion_detalle'],
                'estado': o['estado']
            })
    return jsonify(eventos_json)

@app.route('/api/eventos', methods=['POST'])
def api_crear_evento():
    data = request.get_json()
    titulo = data.get('title', '')
    descripcion = data.get('descripcion', '')
    categoria = data.get('categoria', '')
    fecha_inicio = parse_to_iso(data.get('start'))
    fecha_final = parse_to_iso(data.get('end'))
    repeticion = data.get('repeticion', 'ninguna')
    repeticion_detalle = data.get('repeticion_detalle', '')
    estado = data.get('estado', 'pendiente')
    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    cur = conn.execute('''INSERT INTO eventos (titulo, descripcion, categoria, fecha_inicio, fecha_final, fecha_creacion, fecha_edicion, repeticion, repeticion_detalle, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (titulo, descripcion, categoria, fecha_inicio, fecha_final, fecha, fecha, repeticion, repeticion_detalle, estado))
    conn.commit()
    evento_id = cur.lastrowid
    conn.close()
    return jsonify({'id': evento_id}), 201

@app.route('/api/eventos/<int:evento_id>', methods=['PUT'])
def api_editar_evento(evento_id):
    data = request.get_json()
    titulo = data.get('title', '')
    descripcion = data.get('descripcion', '')
    categoria = data.get('categoria', '')
    fecha_inicio = parse_to_iso(data.get('start'))
    fecha_final = parse_to_iso(data.get('end'))
    repeticion = data.get('repeticion', 'ninguna')
    repeticion_detalle = data.get('repeticion_detalle', '')
    estado = data.get('estado', 'pendiente')
    fecha_edicion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute('''UPDATE eventos SET titulo=?, descripcion=?, categoria=?, fecha_inicio=?, fecha_final=?, fecha_edicion=?, repeticion=?, repeticion_detalle=?, estado=? WHERE id=?''',
                 (titulo, descripcion, categoria, fecha_inicio, fecha_final, fecha_edicion, repeticion, repeticion_detalle, estado, evento_id))
    # Remove old occurrences that don't match the new start date
    conn.execute('DELETE FROM evento_ocurrencias WHERE evento_id=? AND fecha_inicio!=?', (evento_id, fecha_inicio))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/eventos/<int:evento_id>', methods=['DELETE'])
def api_eliminar_evento(evento_id):
    conn = get_db()
    conn.execute('DELETE FROM eventos WHERE id=?', (evento_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'deleted'})

@app.route('/api/notas/<int:nota_id>', methods=['DELETE'])
def api_eliminar_nota(nota_id):
    conn = get_db()
    conn.execute('DELETE FROM notas WHERE id=?', (nota_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'deleted'})

@app.route('/api/notas/<int:nota_id>', methods=['PUT'])
def api_editar_nota(nota_id):
    data = request.get_json()
    titulo = data.get('titulo', '')
    contenido = data.get('contenido', '')
    categoria = data.get('categoria', '')
    utilizada = data.get('utilizada', 'no utilizada')
    fecha_edicion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute('''UPDATE notas SET titulo=?, contenido=?, categoria=?, utilizada=?, fecha_edicion=? WHERE id=?''',
                 (titulo, contenido, categoria, utilizada, fecha_edicion, nota_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/ocurrencia', methods=['POST'])
def api_actualizar_ocurrencia():
    data = request.get_json()
    evento_id = int(data['evento_id'])
    fecha_inicio = normalize_fecha(data['fecha_inicio'])
    fecha_final = normalize_fecha(data['fecha_final'])
    estado = data['estado']
    print(f'DEBUG: Saving ocurrencia: evento_id={evento_id}, fecha_inicio={fecha_inicio}, estado={estado}')
    conn = get_db()
    conn.execute('''
        INSERT INTO evento_ocurrencias (evento_id, fecha_inicio, fecha_final, estado)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(evento_id, fecha_inicio) DO UPDATE SET estado=excluded.estado
    ''', (evento_id, fecha_inicio, fecha_final, estado))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

def parse_to_iso(date_str):
    # Accepts dd/mm/yyyy, HH:mm or ISO
    if not date_str:
        return ''
    # If already ISO, return as is
    if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', date_str):
        return date_str
    # Try dd/mm/yyyy, HH:mm or dd/mm/yyyy HH:mm
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})[ ,] ?(\d{2}):(\d{2})', date_str)
    if m:
        d, mth, y, h, mi = m.groups()
        return f'{y}-{mth}-{d}T{h}:{mi}'
    return date_str

# --- Helper to ensure all datetimes are ISO with T ---
def to_iso_with_T(dt):
    if isinstance(dt, str):
        dt = dt.replace(' ', 'T')
        if 'T' in dt:
            try:
                return datetime.strptime(dt, '%Y-%m-%dT%H:%M')
            except Exception:
                try:
                    return datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S')
                except Exception:
                    return dt
        return dt
    return dt

if __name__ == '__main__':
    app.run(debug=True) 