#pragma once
/**
 * storage.h
 * Manages SD-card file storage for raw SPT data.
 * Data is written as newline-delimited JSON (NDJSON) records.
 * A new file is created for each test session using a timestamp-based name.
 */

#include <Arduino.h>
#include <SD.h>

#define SD_CS_PIN   5           // Chip-select GPIO for SD module
#define MAX_FILENAME_LEN 24

class Storage {
public:
    /**
     * @param csPin  GPIO chip-select pin for the SD card.
     */
    explicit Storage(uint8_t csPin = SD_CS_PIN);

    /** Initialise SD card.  Returns false if the card is absent. */
    bool begin();

    /**
     * Open a new session file.
     * @param sessionId  Numeric ID embedded in the filename.
     * @return true on success.
     */
    bool openSession(uint32_t sessionId);

    /** Append a JSON line to the current open file. */
    bool writeLine(const String &jsonLine);

    /** Flush and close the current file. */
    void closeSession();

    /** Returns the name of the currently open file, or empty string. */
    String currentFilename() const { return String(_filename); }

    /** True when a session file is open and ready to accept data. */
    bool isOpen() const { return _file; }

private:
    uint8_t _csPin;
    File    _file;
    char    _filename[MAX_FILENAME_LEN];
};
