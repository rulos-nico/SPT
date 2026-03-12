# Manual de Usuario – Sistema de Medición SPT

## Inicio rápido

### 1. Instalación del software

```bash
# Clonar el repositorio
git clone https://github.com/rulos-nico/SPT.git
cd SPT/software

# Instalar dependencias Python
pip install -r requirements.txt

# En Ubuntu/Debian instalar tkinter si no está disponible
sudo apt install python3-tk
```

### 2. Conectar el dispositivo

1. Conectar el dispositivo ESP32 a la PC mediante cable USB.
2. Verificar que el sistema operativo asignó un puerto serial:
   - Linux: `/dev/ttyUSB0` o `/dev/ttyACM0`
   - Windows: `COM3`, `COM4`, etc.
   - macOS: `/dev/cu.usbserial-...`

### 3. Iniciar la aplicación

```bash
cd software
python main.py
```

---

## Interfaz gráfica (Dashboard)

### Barra de herramientas (superior)

| Control | Descripción |
|--------|-------------|
| Puerto | Selector desplegable del puerto serial |
| ↻ | Actualizar lista de puertos disponibles |
| Conectar / Desconectar | Abre/cierra la conexión serial |
| ▶ Start Test | Inicia un nuevo ensayo SPT |
| ■ Stop Test | Finaliza el ensayo y guarda los datos |
| Export… | Exporta el ensayo actual a JSON o CSV |
| History | Ver historial de ensayos guardados |

### Panel de configuración del ensayo

Antes de iniciar un ensayo, completar los siguientes campos:

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| Test ID | Identificador único del ensayo | `T001` |
| Borehole | ID del sondeo | `BH-1` |
| Depth (m) | Profundidad al tope del muestreador | `3.0` |
| Location | Nombre del sitio | `Obra Av. San Martín` |
| Operator | Nombre del operador | `J. García` |

### Panel de métricas en tiempo real

| Métrica | Descripción |
|--------|-------------|
| Depth (mm) | Profundidad actual del muestreador |
| Blows (interval) | Golpes en el intervalo actual |
| Total blows | Golpes totales del ensayo |
| N-value | Valor N del ensayo (suma intervalos 1+2) |
| N60 | N-value corregido al 60 % de eficiencia |
| Battery (%) | Nivel de batería del dispositivo |
| Interval | Intervalo activo (Seating / Drive 1 / Drive 2) |

### Control de intervalos

Un ensayo SPT estándar se compone de tres intervalos de 150 mm:

| Botón | Intervalo | Descripción |
|-------|-----------|-------------|
| Seating (0) | 0–150 mm | Intervalo de asentamiento (no se cuenta en N) |
| Drive 1 (1) | 150–300 mm | Primer intervalo de penetración |
| Drive 2 (2) | 300–450 mm | Segundo intervalo de penetración |
| Zero Depth | — | Establece la profundidad actual como cero |
| Hammer η | — | Eficiencia del martillo (default: 0.60) |

---

## Procedimiento de ensayo

### Paso 1 – Preparación

1. Instalar el muestreador en la profundidad de ensayo.
2. Conectar el dispositivo al PC y abrir la aplicación.
3. Seleccionar el puerto y hacer clic en **Conectar**.
4. Verificar que el indicador de estado muestre "● Connected".

### Paso 2 – Configurar el ensayo

1. Completar los campos de **Test Setup** (Test ID, Borehole, Depth, etc.).
2. Configurar la eficiencia del martillo (`Hammer η`) según el tipo de martillo:
   - Martillo manual (cuerda-polea): 0.45
   - Martillo automático tipo donut: 0.60
   - Martillo automático safety: 0.60–0.75
   - Martillo automático trip: 0.72–0.80

### Paso 3 – Intervalo de asentamiento

1. Hacer clic en **Zero Depth** para poner en cero el encoder en la posición inicial.
2. Hacer clic en **Seating (0)** para iniciar el intervalo de asentamiento.
3. Ejecutar los golpes del intervalo de asentamiento (150 mm).
   - El sistema registra cada golpe automáticamente.

### Paso 4 – Intervalos de penetración

1. Al completar los 150 mm del asentamiento, hacer clic en **Drive 1 (1)**.
2. Ejecutar los golpes del primer intervalo de penetración (150 mm).
3. Al completar, hacer clic en **Drive 2 (2)**.
4. Ejecutar los golpes del segundo intervalo de penetración (150 mm).

> **Nota**: Si el muestreador penetra los 300 mm de los dos intervalos con menos de 50 golpes, el ensayo se considera completado. Si se requieren más de 50 golpes en 300 mm, el ensayo puede detenerse anticipadamente registrando el número de golpes y la penetración alcanzada.

### Paso 5 – Finalizar y guardar

1. Hacer clic en **■ Stop Test**.
2. El sistema calcula N-value y N60 automáticamente.
3. Los datos se guardan en la base de datos SQLite local (`spt_measurements.db`).

### Paso 6 – Exportar resultados

1. Hacer clic en **Export…**.
2. Seleccionar formato:
   - **JSON**: datos completos con todos los golpes e intervalos.
   - **CSV**: tabla de golpes (una fila por golpe).
3. Elegir ubicación y nombre del archivo.

---

## Modo demo (sin hardware)

Para probar el sistema sin equipamiento:

```bash
cd software
python main.py --demo
```

El modo demo simula un ensayo completo con datos aleatorios y muestra el resumen en consola.

---

## Base de datos local

Los ensayos se almacenan automáticamente en `software/spt_measurements.db` (SQLite). Para ver el historial:

1. Hacer clic en **History** en la barra de herramientas.
2. Se muestra una tabla con todos los ensayos guardados.

Para acceder a los datos directamente:

```python
from src.storage.database import Database

db = Database("spt_measurements.db")
db.open()

# Listar todos los ensayos
tests = db.list_tests()
for t in tests:
    print(f"{t.test_id}: N={t.n_value()}, N60={t.n60()}")

db.close()
```

---

## Exportación desde línea de comandos

```python
from src.storage.database import Database
from src.storage.exporter import Exporter

with Database("spt_measurements.db") as db:
    test = db.load_test("T001")
    if test:
        Exporter.to_json(test, "T001_completo.json")
        Exporter.to_csv_blows(test, "T001_golpes.csv")
        Exporter.to_csv_intervals(test, "T001_intervalos.csv")
    
    all_tests = db.list_tests()
    Exporter.to_csv_summary(all_tests, "resumen_todos.csv")
    Exporter.tests_to_json(all_tests, "todos_los_ensayos.json")
```

---

## Generación de gráficos

```python
from src.visualization.charts import (
    plot_blows_vs_depth,
    plot_depth_vs_time,
    plot_impact_acceleration,
    plot_n_profile,
    save_figure,
)
from src.storage.database import Database

with Database("spt_measurements.db") as db:
    test = db.load_test("T001")
    tests = db.list_tests()

# Gráfico de golpes por intervalo
fig = plot_blows_vs_depth(test)
save_figure(fig, "golpes_T001.png")

# Perfil de penetración vs tiempo
fig = plot_depth_vs_time(test)
save_figure(fig, "penetracion_T001.png")

# Aceleración de impacto
fig = plot_impact_acceleration(test)
save_figure(fig, "impacto_T001.png")

# Perfil N60 del sondeo
fig = plot_n_profile(tests, use_n60=True)
save_figure(fig, "perfil_N60_BH1.png")
```

---

## Resolución de problemas

| Problema | Solución |
|---------|---------|
| No aparecen puertos en el selector | Verificar que el driver USB-Serial está instalado. En Linux: `ls /dev/ttyUSB*` |
| "ADXL345 not found" | Verificar conexión I²C. Medir voltaje en SDA/SCL (deben ser ~3.3V en reposo) |
| "SD card not found" | Verificar que la tarjeta está formateada en FAT32 y correctamente insertada |
| Golpes no detectados | Aumentar el umbral (`IMPACT_THRESHOLD_G`) o reducir el rebote (`BLOW_DEBOUNCE_MS`) |
| Profundidad incorrecta | Verificar el factor `MM_PER_REV` según la mecánica de acoplamiento del encoder |
| "RTC not found" | Verificar conexión I²C. Si el reloj perdió la hora, se ajusta automáticamente |
| tkinter no disponible | `sudo apt install python3-tk` (Linux) |
| pyserial no instalado | `pip install pyserial` |

---

## Especificaciones técnicas

| Parámetro | Valor |
|----------|-------|
| Rango de detección de impactos | 1–16g |
| Umbral de impacto (default) | 5g sobre línea base |
| Resolución de penetración | 0.0033 mm/pulso |
| Frecuencia de muestreo acelerómetro | 100 Hz |
| Tasa de actualización de profundidad | 2 Hz (cada 500 ms) |
| Baudrate serial | 115200 |
| Formato de datos | JSON por líneas (NDJSON) |
| Base de datos | SQLite 3 |
| Formatos de exportación | JSON, CSV |
