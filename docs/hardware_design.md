# Diseño de Hardware – Sistema de Medición SPT

## Arquitectura del sistema

El sistema de medición SPT está basado en un microcontrolador ESP32 que actúa como unidad central de adquisición de datos. El ESP32 se comunica con los sensores mediante los buses I²C y GPIO, almacena los datos localmente en una tarjeta SD y transmite los eventos en tiempo real a la PC de registro mediante USB-Serial.

```
                    ┌─────────────────────────────────────┐
                    │           ESP32 DevKit               │
                    │                                     │
  ADXL345 ──I²C──▶│ GPIO 21 (SDA)                       │
  DS3231  ──I²C──▶│ GPIO 22 (SCL)                       │
                    │                                     │
  Encoder A ───────▶│ GPIO 34 (INT)   GPIO 5 ───▶ SD CS  │
  Encoder B ───────▶│ GPIO 35         GPIO 2 ───▶ LED    │
                    │                 GPIO 4 ───▶ Buzzer  │
                    │                                     │──USB──▶ PC
                    │ SPI: GPIO 18 (CLK)                  │
                    │      GPIO 19 (MISO)                 │
                    │      GPIO 23 (MOSI)                 │
                    └─────────────────────────────────────┘
```

## Sensores

### 1. Acelerómetro ADXL345 – Detección de impactos

El ADXL345 es un acelerómetro de 3 ejes con rango configurable de ±2g a ±16g y resolución de 13 bits. Se utiliza en modo I²C a 400 kHz.

**Configuración:**
- Rango: ±16g (modo ADXL345_RANGE_16_G)
- Tasa de muestreo: 100 Hz (configurable por firmware)
- Umbral de detección: 5g sobre la línea base (configurable)
- Tiempo de rebote: 200 ms (configurable)

**Instalación mecánica:**
El sensor debe montarse rígidamente sobre la varilla de perforación o la cabeza del muestreador, con el eje Z alineado con la dirección del impacto (eje longitudinal de la varilla). Se recomienda encapsulado resistente a vibraciones y polvo (IP65 o superior).

**Calibración de línea base:**
Al inicializar el sistema, el firmware toma 50 muestras en reposo y calcula la magnitud media de la aceleración gravitacional como referencia. Un impacto se registra cuando la magnitud supera la línea base en más del umbral configurado.

### 2. Encoder rotativo cuadratura – Medición de penetración

Se utiliza un encoder óptico incremental de 600 pulsos/rev con salida A/B en cuadratura. El encoder se acopla mecánicamente a una cremallera o cable metálico unido al cabezal del muestreador.

**Configuración:**
- Resolución: 600 PPR
- Factor de conversión: 2 mm/rev (acoplamiento por cremallera)
- Resolución efectiva: 0.0033 mm/pulso
- Decodificación: X1 (flanco de subida/bajada del canal A)

**Instalación:**
El encoder debe montarse en una estructura fija (torre o cabezal), con el eje acoplado a la varilla o cable que sigue el movimiento del muestreador. Se requiere una guía lineal para garantizar movimiento suave y sin holguras.

### 3. RTC DS3231 – Marcación temporal

El DS3231 es un reloj de tiempo real de alta precisión (±2 ppm) con compensación de temperatura integrada. Se comunica por I²C y comparte el bus con el ADXL345.

**Uso:**
- Proporciona timestamp Unix en cada evento registrado
- Se inicializa con la fecha/hora del sistema en el primer arranque
- La batería de respaldo (CR2032) mantiene la hora durante cortes de energía

### 4. Tarjeta SD – Almacenamiento local

Módulo SPI con soporte para tarjetas FAT32. Almacena los datos como archivos de texto con registros JSON delimitados por salto de línea (NDJSON).

**Formato de archivo:**
```
/SPT00001.txt   ← sesión 1
/SPT00002.txt   ← sesión 2
...
```

Cada archivo contiene una línea JSON por evento:
```
{"type":"blow","ts":1700000010,"blow":5,"depth_mm":225.0,"impact_g":8.45}
{"type":"depth","ts":1700000011,"depth_mm":227.3}
```

## Esquema de conexiones ESP32

| Señal | Pin ESP32 | Componente |
|-------|-----------|-----------|
| SDA | GPIO 21 | ADXL345 + DS3231 |
| SCL | GPIO 22 | ADXL345 + DS3231 |
| Encoder A | GPIO 34 | Encoder (interrupción) |
| Encoder B | GPIO 35 | Encoder (dirección) |
| SD CS | GPIO 5 | Módulo SD |
| SD CLK | GPIO 18 | Módulo SD |
| SD MISO | GPIO 19 | Módulo SD |
| SD MOSI | GPIO 23 | Módulo SD |
| LED | GPIO 2 | LED indicador |
| Buzzer | GPIO 4 | Buzzer activo |
| USB | USB-UART | PC de registro |

## Alimentación

El sistema puede alimentarse de:
- **USB-C** (5V desde el PC de registro): adecuado para uso con cable corto
- **Batería LiPo 3.7V** + regulador 3.3V: para uso en campo sin cable
- **Batería 12V** + regulador 5V: para instalaciones en camiones de perforación

**Consumo estimado:**
| Modo | Corriente |
|------|-----------|
| Activo (sensado + serial) | ~150 mA |
| Standby (sin SD write) | ~80 mA |

## Consideraciones de instalación en campo

1. **Protección ambiental**: El enclosure debe ser al menos IP65. Se recomienda IP67 para ambientes con agua o barro.
2. **Cableado**: Usar cable apantallado para las señales del encoder y del acelerómetro. Longitud máxima recomendada: 2 m para I²C.
3. **Montaje del acelerómetro**: Fijación rígida al cuerpo del muestreador o cabezal de la varilla, perpendicular al plano de impacto.
4. **Montaje del encoder**: Sistema de guía lineal con resorte de tensión para mantener contacto constante con la varilla.
5. **Puesta a tierra**: El chasis metálico del equipo debe conectarse a tierra para evitar interferencias electromagnéticas.
