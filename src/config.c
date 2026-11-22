#include <stdlib.h>
#include <string.h>
#include "config.h"
#include "checksum.h"

// The remote the command uses: the irlingo command sends one remote at a
// time. ESPHome and other targets use irRemote handles directly.
static irRemote *REMOTE = 0;
static char *CONFIGFILEPATH = 0;

void unloadConfig() {
  irRemoteFree(REMOTE);
  REMOTE = 0;
  free(CONFIGFILEPATH);
  CONFIGFILEPATH = 0;
}

// Make a parsed remote the loaded one; NULL leaves the previous one loaded
static void useRemote(irRemote *remote, const char *path) {
  if (!remote)
    return;
  unloadConfig();
  REMOTE = remote;
  CONFIGFILEPATH = path ? strdup(path) : 0;
}

void loadConfig(const char *configfilepath) {
  if (CONFIGFILEPATH && configfilepath && strcmp(configfilepath, CONFIGFILEPATH) == 0)
    return;
  useRemote(irRemoteParseFile(configfilepath), configfilepath);
}

void loadConfigString(const char *json) {
  // Text is parsed every time; "(text)" names it in messages
  useRemote(irRemoteParse(json, "(text)"), 0);
}

int isConfigLoaded() { return REMOTE != 0; }

irRemote *loadedRemote(void) { return REMOTE; }

size_t getSymboldefinitionsCount() { return REMOTE ? irRemoteSymbolCount(REMOTE) : 0; }

size_t getAllFeaturesCount() { return REMOTE ? irRemoteFeatureCount(REMOTE) : 0; }

const char *getFeatureName(size_t index) { return REMOTE ? irRemoteFeatureName(REMOTE, index) : 0; }

int getFeatureIndex(const char *featureName, size_t *index) {
  return REMOTE && irRemoteFeatureIndex(REMOTE, featureName, index);
}

size_t getFeatureValuesCount(size_t nameIndex) { return REMOTE ? irRemoteFeatureValueCount(REMOTE, nameIndex) : 0; }

const char *getFeatureValueName(size_t nameIndex, size_t valueIndex) {
  return REMOTE ? irRemoteFeatureValueName(REMOTE, nameIndex, valueIndex) : 0;
}

int hasFeatureNameAndValue(const char *featureName, const char *featureValue) {
  return REMOTE && irRemoteHasFeature(REMOTE, featureName, featureValue);
}

void loadConfigSymbols(symbolDefinition configSymbols[]) {
  if (REMOTE)
    irRemoteSymbols(REMOTE, configSymbols);
}

void loadTemplateCode(const char **symbolString) { *symbolString = REMOTE ? irRemoteTemplate(REMOTE) : 0; }

void loadFeaturedCode(const featureT *features, char **featuredCode) {
  loadToggledFeaturedCode(features, 0, featuredCode);
}

int hasToggle() { return REMOTE && irRemoteHasToggle(REMOTE); }

void loadToggledFeaturedCode(const featureT *features, int toggled, char **featuredCode) {
  *featuredCode = 0;
  if (!REMOTE)
    return;
  size_t size = irRemoteMaxCodeLength(REMOTE) + 1;
  *featuredCode = (char *) malloc(size);
  if (*featuredCode && irRemoteEncode(REMOTE, features, toggled, *featuredCode, size)) {
    free(*featuredCode);
    *featuredCode = 0;
  }
}

void loadOutPin(unsigned int *outPin) { *outPin = REMOTE ? irRemoteOutPin(REMOTE) : 0; }

void loadDescription(const char **description) { *description = REMOTE ? irRemoteDescription(REMOTE) : 0; }

void loadDevice(const char **device) { *device = REMOTE ? irRemoteDevice(REMOTE) : 0; }

void loadPlugin(const char **plugin) { *plugin = REMOTE ? irRemotePlugin(REMOTE) : 0; }

void loadFrequency(int *frequency) { *frequency = REMOTE ? irRemoteFrequency(REMOTE) : 0; }

void loadDutyCycle(double *dutycycle) { *dutycycle = REMOTE ? irRemoteDutyCycle(REMOTE) : 0; }

const JSON_Array *loadChecksums(void) { return REMOTE ? irRemoteChecksums(REMOTE) : 0; }

int hasVariants(void) { return REMOTE && irRemoteHasVariants(REMOTE); }

int applyConfigChecksums(char *code) {
  const JSON_Array *checksums = loadChecksums();
  if (!json_array_get_count(checksums))
    return 0;
  size_t *bitPos = (size_t *) malloc((strlen(code) + 1) * sizeof(size_t));
  if (!bitPos)
    return 1;
  int result = applyChecksums(checksums, code, bitPos);
  free(bitPos);
  return result;
}
