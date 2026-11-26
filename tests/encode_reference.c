// The codes and pulses irlingo's C core sends, as a reference for the Python
// encoder of the Home Assistant integration (test_python_encoder.py).
//
// usage: encode_reference REMOTE.json < REQUESTS
// Each line of REQUESTS is "TOGGLED<TAB>NAME=VALUE<TAB>...", TOGGLED 0 or 1.
// For each, it prints "CODE|PULSES" with the pulses and spaces in
// microseconds, spaces negative, or "ERROR" when a checksum, the plugin or
// the pulses fail.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "config.h"
#include "checksum.h"
#include "plugins.h"
#include "pulses.h"
#include "log.h"

int main(int argc, char *argv[]) {
  if (argc != 2) {
    fprintf(stderr, "usage: %s REMOTE.json < REQUESTS\n", argv[0]);
    return 2;
  }
  log_set_quiet(true);
  loadConfig(argv[1]);
  if (!isConfigLoaded())
    return 2;
  const char *plugin = NULL;
  loadPlugin(&plugin);
  if (!plugin && !loadChecksums() && !hasVariants())
    plugin = legacyRemotePlugin(argv[1]);

  size_t featureCount = getAllFeaturesCount();
  size_t symbolCount = getSymboldefinitionsCount();
  symbolDefinition *symbols = calloc(symbolCount ? symbolCount : 1, sizeof(symbolDefinition));
  loadConfigSymbols(symbols);
  featureT *features = calloc(featureCount ? featureCount : 1, sizeof(featureT));
  static char line[1 << 16];
  static unsigned int pulses[MAX_PULSE_VALUES];

  while (fgets(line, sizeof(line), stdin)) {
    memset(features, 0, (featureCount ? featureCount : 1) * sizeof(featureT));
    char *field = strtok(line, "\t\r\n");
    int toggled = field ? atoi(field) : 0;
    while ((field = strtok(NULL, "\t\r\n"))) {
      char *value = strchr(field, '=');
      size_t index = 0;
      if (!value) {
        fprintf(stderr, "Not NAME=VALUE: %s\n", field);
        return 2;
      }
      *value++ = 0;
      if (getFeatureIndex(field, &index)) {
        features[index].name = field;
        features[index].value = value;
      }
    }

    char *code = NULL;
    size_t count = 0;
    loadToggledFeaturedCode(features, toggled, &code);
    if (!code || applyConfigChecksums(code) || applyRemotePlugin(plugin, code) ||
        irlingoBuildPulses(symbolCount, symbols, code, pulses, &count)) {
      printf("ERROR\n");
    } else {
      printf("%s|", code);
      for (size_t i = 0; i < count; i++)
        printf(i ? ",%d" : "%d", i % 2 ? -(int) pulses[i] : (int) pulses[i]);
      printf("\n");
    }
    free(code);
  }
  free(features);
  free(symbols);
  unloadConfig();
  return 0;
}
