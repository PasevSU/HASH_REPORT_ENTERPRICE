// ChronoSeal declarative JS rules; evaluated in restricted VM.
module.exports = {
  "id": "file_information",
  "type": "file_information",
  "title": "FILE INFORMATION:",
  "style": "file_information",
  "fields": [
    "name",
    "size_kb",
    "created",
    "modified",
    "sha256",
    "hardware_id",
    "report_id"
  ],
  "size_display": {
    "unit": "KB",
    "decimal_places": 3
  },
  "version": 1
};
