#ifndef IRREMOTE_H
#define IRREMOTE_H

// A remote: its JSON definition, parsed once, and the functions turning
// feature values into a code (a string of symbols). Every function works on
// the remote it is given, so any number of remotes can be used at once.
// Encoding allocates nothing; parsing and freeing a remote do.

#include <stddef.h>
#include "symboldefinition.h"
#include "parson.h"

/// A requested feature value, e.g. name "mode" and value "HEAT"
typedef struct q {
  const char *name;
  const char *value;
} featureT;

/// A parsed remote (opaque): irRemoteParse() makes one, irRemoteFree() frees it
typedef struct irRemote irRemote;

/// Parse a remote from JSON text or a file. name names it in messages.
/// Returns NULL (logged) when it is not a JSON object.
irRemote *irRemoteParse(const char *json, const char *name);
irRemote *irRemoteParseFile(const char *path);
void irRemoteFree(irRemote *remote);
const char *irRemoteName(const irRemote *remote);

// Features: names in the order of the remote, and their values
size_t irRemoteFeatureCount(const irRemote *remote);
const char *irRemoteFeatureName(const irRemote *remote, size_t index);
/// Returns 1 and the index of the feature in *index when the remote has it
int irRemoteFeatureIndex(const irRemote *remote, const char *name, size_t *index);
size_t irRemoteFeatureValueCount(const irRemote *remote, size_t index);
const char *irRemoteFeatureValueName(const irRemote *remote, size_t index, size_t valueIndex);
int irRemoteHasFeature(const irRemote *remote, const char *name, const char *value);

size_t irRemoteSymbolCount(const irRemote *remote);
/// Fill symbols, irRemoteSymbolCount() entries
void irRemoteSymbols(const irRemote *remote, symbolDefinition symbols[]);

const char *irRemoteTemplate(const irRemote *remote);
const char *irRemoteDescription(const irRemote *remote);
const char *irRemoteDevice(const irRemote *remote);
const char *irRemotePlugin(const irRemote *remote);
int irRemoteFrequency(const irRemote *remote);
double irRemoteDutyCycle(const irRemote *remote);
unsigned int irRemoteOutPin(const irRemote *remote);
int irRemoteHasToggle(const irRemote *remote);
int irRemoteHasVariants(const irRemote *remote);

/// The length of the longest code the remote can encode: its longest
/// template, its own or a variant's. A code buffer needs one more char.
size_t irRemoteMaxCodeLength(const irRemote *remote);

/// Write the code for these features into code, a buffer of size chars
/// (irRemoteMaxCodeLength() + 1 is always enough). Features are applied to
/// the template, then the "overrides" whose features are all requested. When
/// the "when" features of one of the "variants" are all requested, the first
/// such variant's template, features, overrides (and checksums, see
/// irRemoteChecksums()) are used instead. features holds up to
/// irRemoteFeatureCount() entries, unused ones with a NULL value, or is NULL
/// for the template alone. Features are applied in the order of the remote,
/// so a feature defined later (e.g. an option forcing a fan speed) overrides
/// an earlier one regardless of the order they were requested in. If a
/// feature is requested more than once, the last request is used. When
/// toggled is set, a feature value that has a code in the "toggle" section
/// uses that code instead: remotes with a toggle bit send it on every other
/// press. Returns 0, or 1 when the code does not fit (logged).
int irRemoteEncode(irRemote *remote, const featureT *features, int toggled, char *code, size_t size);

/// The "checksums" array of the definition (the remote or one of its
/// variants) the last irRemoteEncode() used, NULL when it has none (see
/// checksum.h)
const JSON_Array *irRemoteChecksums(const irRemote *remote);

#endif
