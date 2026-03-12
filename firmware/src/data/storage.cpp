/**
 * storage.cpp
 * Implementation of SD-card storage manager.
 */

#include "storage.h"

Storage::Storage(uint8_t csPin)
    : _csPin(csPin)
{
    _filename[0] = '\0';
}

bool Storage::begin() {
    return SD.begin(_csPin);
}

bool Storage::openSession(uint32_t sessionId) {
    if (_file) {
        _file.close();
    }
    // Filename format: SPTxxxxx.ndjson (8.3 compatible on FAT)
    snprintf(_filename, sizeof(_filename), "/SPT%05lu.txt",
             static_cast<unsigned long>(sessionId));
    _file = SD.open(_filename, FILE_WRITE);
    return static_cast<bool>(_file);
}

bool Storage::writeLine(const String &jsonLine) {
    if (!_file) {
        return false;
    }
    _file.println(jsonLine);
    return true;
}

void Storage::closeSession() {
    if (_file) {
        _file.flush();
        _file.close();
    }
}
