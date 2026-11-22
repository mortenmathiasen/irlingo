// The log messages of irlingo's portable C code go to ESPHome's log. On
// Linux, log_log() is rxi's log.c (src/log.c).
#include <cstdarg>

#include "esphome/core/log.h"

extern "C" {
#include "log.h"
}

namespace esphome::irlingo {

static const char *const TAG = "irlingo";

static int esphome_level(int level) {
  if (level >= LOG_ERROR)
    return ESPHOME_LOG_LEVEL_ERROR;
  if (level == LOG_WARN)
    return ESPHOME_LOG_LEVEL_WARN;
  if (level == LOG_INFO)
    return ESPHOME_LOG_LEVEL_DEBUG;
  return ESPHOME_LOG_LEVEL_VERBOSE;
}

}  // namespace esphome::irlingo

extern "C" void log_log(int level, const char *file, int line, const char *fmt, ...) {  // NOLINT
  (void) file;
  int esp_level = esphome::irlingo::esphome_level(level);
  if (esp_level > ESPHOME_LOG_LEVEL)
    return;
  va_list args;
  va_start(args, fmt);
  esphome::esp_log_vprintf_(esp_level, esphome::irlingo::TAG, line, fmt, args);
  va_end(args);
}
