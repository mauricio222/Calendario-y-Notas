import sqlite3

conn = sqlite3.connect('calendario_notas.db')
c = conn.cursor()

# Crear tabla notas
c.execute('''
CREATE TABLE IF NOT EXISTS notas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    contenido TEXT NOT NULL,
    categoria TEXT NOT NULL,
    fecha_creacion DATETIME NOT NULL,
    fecha_edicion DATETIME NOT NULL,
    utilizada TEXT NOT NULL DEFAULT 'no utilizada'
)
''')

# Crear tabla eventos
c.execute('''
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    categoria TEXT NOT NULL,
    fecha_inicio DATETIME NOT NULL,
    fecha_final DATETIME NOT NULL,
    fecha_creacion DATETIME NOT NULL,
    fecha_edicion DATETIME NOT NULL,
    repeticion TEXT NOT NULL,
    repeticion_detalle TEXT,
    estado TEXT NOT NULL
)
''')

# Crear tabla evento_ocurrencias
c.execute('''
CREATE TABLE IF NOT EXISTS evento_ocurrencias (
    evento_id INTEGER NOT NULL,
    fecha_inicio DATETIME NOT NULL,
    fecha_final DATETIME NOT NULL,
    estado TEXT NOT NULL,
    PRIMARY KEY (evento_id, fecha_inicio),
    FOREIGN KEY (evento_id) REFERENCES eventos(id)
)
''')

conn.commit()
conn.close() 