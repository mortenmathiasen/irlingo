#ifndef CONFIG_H
#define CONFIG_H

// The irlingo command's remote: one remote at a time, loaded from a file
// or JSON text, on top of the portable irRemote functions (irremote.h).

#include "irremote.h"

//Load configuration from file
void loadConfig(const char *configfilepath);
// Load configuration from JSON text, e.g. a remote built into firmware.
// Like loadConfig(), a remote that cannot be parsed leaves the previous one
// loaded.
void loadConfigString(const char *json);
void unloadConfig();
int isConfigLoaded();
// The loaded remote, NULL when none is
irRemote *loadedRemote(void);

size_t getSymboldefinitionsCount();

size_t getAllFeaturesCount();
const char * getFeatureName(size_t index);
int getFeatureIndex(const char *featureName, size_t *index);

size_t getFeatureValuesCount(size_t nameIndex);
const char * getFeatureValueName(size_t nameIndex, size_t valueIndex);
int hasFeatureNameAndValue(const char *featureName, const char *featureValue);

void loadConfigSymbols(symbolDefinition configSymbols[]);
void loadTemplateCode(const char **symbolString);
// The code for these features (see irRemoteEncode()), allocated: free it
void loadFeaturedCode(const featureT *features,
		      char **featuredCode);
int hasToggle();
void loadToggledFeaturedCode(const featureT *features, int toggled,
			     char **featuredCode);
void loadOutPin(unsigned int *outPin);  //Output
void loadDescription(const char **description);
void loadDevice(const char **device);
void loadPlugin(const char **plugin);
void loadFrequency(int *frequency);
void loadDutyCycle(double *dutycycle);
// The "checksums" array of the definition (the remote or one of its
// variants) the last loadFeaturedCode() used, NULL when it has none (see
// checksum.h)
const JSON_Array *loadChecksums(void);
int hasVariants(void);

// Apply the checksums of the loaded remote, if it has any (see
// applyChecksums())
int applyConfigChecksums(char *code);

#endif
