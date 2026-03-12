# SPT
Sistema para la medición digital del ensayo SPT (Standard Penetration Test). El proyecto se enfoca en la instrumentación del ensayo mediante sensores, sistemas de adquisición de datos y procesamiento digital para registrar golpes, penetración y eventos del ensayo, mejorando la precisión, trazabilidad y gestión de la información geotécnica.

---

## Descripción general

El sistema está compuesto por dos subsistemas integrados:

| Subsistema | Tecnología | Descripción |
|-----------|-----------|-------------|
| **Firmware embebido** | C++ / Arduino (ESP32) | Adquiere datos de sensores en tiempo real y los envía por serial JSON |
| **Software de escritorio** | Python 3 | Recibe, procesa, visualiza, almacena y exporta los datos del ensayo |

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Sistema SPT                                   │
│                                                                      │
│  ┌─────────────────────┐          ┌──────────────────────────────┐  │
│  │   Hardware / Firmware│          │    Software PC (Python)      │  │
│  │                     │          │                              │  │
│  │  ADXL345            │          │  Dashboard (tkinter)         │  │
│  │  (acelerómetro)     │  Serial  │  DataProcessor               │  │
│  │  Encoder rotativo   │ ──JSON──▶│  Database (SQLite)           │  │
│  │  RTC DS3231         │          │  Exporter (CSV / JSON)       │  │
│  │  Tarjeta SD         │          │  Charts (matplotlib)         │  │
│  │  ESP32 / Arduino    │          │                              │  │
│  └─────────────────────┘          └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Estructura del proyecto

```
SPT/
├── firmware/                   # Firmware embebido (C++ / PlatformIO)
│   ├── platformio.ini          # Configuración PlatformIO (ESP32 / Arduino Mega)
│   └── src/
│       ├── main.cpp            # Loop principal del microcontrolador
│       ├── sensors/
│       │   ├── impact_sensor.h/.cpp       # Detección de impactos (ADXL345)
│       │   └── penetration_sensor.h/.cpp  # Profundidad (encoder rotativo)
│       ├── data/
│       │   └── storage.h/.cpp             # Almacenamiento en tarjeta SD
│       └── comm/
│           └── protocol.h/.cpp            # Protocolo serial JSON
│
├── software/                   # Aplicación de escritorio (Python 3)
│   ├── main.py                 # Punto de entrada (GUI o modo demo)
│   ├── requirements.txt        # Dependencias Python
│   ├── pytest.ini              # Configuración de tests
│   ├── src/
│   │   ├── models/
│   │   │   └── spt_test.py         # Modelos de datos (Blow, SPTInterval, SPTTest)
│   │   ├── acquisition/
│   │   │   ├── data_processor.py   # Procesamiento de eventos del ensayo
│   │   │   └── serial_reader.py    # Lectura serial en hilo de fondo
│   │   ├── storage/
│   │   │   ├── database.py         # Base de datos SQLite
│   │   │   └── exporter.py         # Exportación CSV / JSON
│   │   └── visualization/
│   │       ├── charts.py           # Gráficos matplotlib
│   │       └── dashboard.py        # Dashboard GUI (tkinter + matplotlib)
│   └── tests/
│       ├── test_spt_models.py      # Tests del modelo de datos
│       ├── test_data_processor.py  # Tests del procesador
│       ├── test_database.py        # Tests de la base de datos
│       └── test_exporter.py        # Tests de exportación
│
└── docs/
    ├── hardware_design.md      # Diseño de hardware y conexiones
    └── user_manual.md          # Manual de usuario
```

---

## Hardware

### Componentes requeridos

| Componente | Modelo | Función |
|-----------|--------|---------|
| Microcontrolador | ESP32 DevKit (o Arduino Mega) | Procesamiento central |
| Acelerómetro | ADXL345 (I²C) | Detección de impactos del martillo |
| Encoder rotativo | 600 PPR, cuadratura | Medición de penetración |
| RTC | DS3231 (I²C) | Marca temporal de eventos |
| Almacenamiento | Módulo SD card | Respaldo local de datos |
| Indicadores | LED + buzzer | Confirmación visual/sonora de golpe |

### Conexiones (ESP32)

```
ADXL345 / DS3231  →  SDA: GPIO 21,  SCL: GPIO 22
Encoder A         →  GPIO 34  (interrupción)
Encoder B         →  GPIO 35
SD card CS        →  GPIO 5
LED indicador     →  GPIO 2
Buzzer            →  GPIO 4
```

### Compilación del firmware

```bash
# Instalar PlatformIO
pip install platformio

# Compilar y flashear (ESP32)
cd firmware
pio run -e esp32dev -t upload

# Monitor serial
pio device monitor -b 115200
```

---

## Software

### Instalación

```bash
cd software
pip install -r requirements.txt
```

### Ejecutar la aplicación GUI

```bash
cd software
python main.py
```

> **Nota**: Requiere `tkinter` (incluido en Python estándar) y `matplotlib`.  
> En Ubuntu/Debian: `sudo apt install python3-tk`

### Modo demo (sin hardware)

```bash
cd software
python main.py --demo
```

### Ejecutar los tests

```bash
cd software
python -m pytest tests/ -v
```

---

## Protocolo de comunicación

El firmware envía mensajes JSON por puerto serial (115200 baud). Cada mensaje termina con `\n`.

### Mensajes del dispositivo al PC

```jsonc
// Golpe detectado
{"type": "blow", "ts": 1700000010, "blow": 5, "depth_mm": 225.0, "impact_g": 8.45}

// Actualización periódica de profundidad (cada 500 ms)
{"type": "depth", "ts": 1700000011, "depth_mm": 227.3}

// Heartbeat del dispositivo (cada 5 s)
{"type": "status", "ts": 1700000015, "battery_pct": 92, "free_mem_kb": 180}
```

### Comandos del PC al dispositivo

```jsonc
{"cmd": "start"}   // Iniciar ensayo
{"cmd": "stop"}    // Detener ensayo
{"cmd": "reset"}   // Reiniciar contadores
{"cmd": "zero"}    // Cero de profundidad
```

---

## Modelo de datos SPT

### N-value (valor N)

Suma de golpes en los dos intervalos de penetración (descartando el intervalo de asentamiento):

```
N = golpes_intervalo_1 + golpes_intervalo_2
```

### N60 (corrección de energía)

```
N60 = N × (Em × Cb × Cs × Cr) / 0.60
```

| Símbolo | Factor | Valor típico |
|--------|--------|-------------|
| Em | Eficiencia del martillo | 0.45–0.80 |
| Cb | Corrección diámetro de sondeo | 1.00–1.15 |
| Cs | Corrección del muestreador | 1.00–1.30 |
| Cr | Corrección longitud de varillas | 0.75–1.00 |

### Exportación de datos

```python
from src.storage.exporter import Exporter

# JSON completo
Exporter.to_json(test, "ensayo_T001.json")

# CSV con un golpe por fila
Exporter.to_csv_blows(test, "golpes_T001.csv")

# CSV resumen por intervalo
Exporter.to_csv_intervals(test, "intervalos_T001.csv")

# CSV resumen de múltiples ensayos
Exporter.to_csv_summary(tests, "resumen_bh1.csv")
```

---

## Licencia

MIT

