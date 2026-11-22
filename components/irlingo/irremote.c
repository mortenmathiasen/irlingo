#include <stdlib.h>
#include <string.h>
#include "irremote.h"
#include "parson.h"
#include "log.h"

struct irRemote {
  JSON_Value *value;
  JSON_Object *root;
  // The definition (the remote itself or one of its "variants") the last
  // irRemoteEncode() used
  JSON_Object *selected;
  char *name;
};

// A parsed remote, or NULL when it is not a JSON object
static irRemote *useValue(JSON_Value *value, const char *name) {
  if (json_value_get_type(value) != JSONObject) {
    log_error("JSON file %s root not an object", name);
    if (value)
      json_value_free(value);
    return NULL;
  }
  irRemote *remote = (irRemote *) calloc(1, sizeof(irRemote));
  char *copy = strdup(name);
  if (!remote || !copy) {
    log_error("Out of memory loading %s", name);
    free(remote);
    free(copy);
    json_value_free(value);
    return NULL;
  }
  remote->value = value;
  remote->root = json_value_get_object(value);
  remote->name = copy;
  return remote;
}

irRemote *irRemoteParse(const char *json, const char *name) {
  return useValue(json ? json_parse_string(json) : NULL, name ? name : "(text)");
}

irRemote *irRemoteParseFile(const char *path) {
  return useValue(path ? json_parse_file(path) : NULL, path ? path : "(no file)");
}

void irRemoteFree(irRemote *remote) {
  if (!remote)
    return;
  json_value_free(remote->value);
  free(remote->name);
  free(remote);
}

const char *irRemoteName(const irRemote *remote) { return remote->name; }

static JSON_Object *featuresObject(const irRemote *remote) {
  JSON_Object *features = json_object_get_object(remote->root, "features");
  if (!features)
    log_error("JSON file %s features object within root object", remote->name);
  return features;
}

size_t irRemoteFeatureCount(const irRemote *remote) { return json_object_get_count(featuresObject(remote)); }

const char *irRemoteFeatureName(const irRemote *remote, size_t index) {
  return json_object_get_name(featuresObject(remote), index);
}

static JSON_Object *featureObject(const irRemote *remote, size_t index) {
  JSON_Object *features = featuresObject(remote);
  return json_object_get_object(features, json_object_get_name(features, index));
}

int irRemoteFeatureIndex(const irRemote *remote, const char *name, size_t *index) {
  size_t count = irRemoteFeatureCount(remote);
  for (size_t i = 0; i < count; i++) {
    if (strcmp(name, irRemoteFeatureName(remote, i)) == 0) {
      *index = i;
      return 1;
    }
  }
  return 0;
}

size_t irRemoteFeatureValueCount(const irRemote *remote, size_t index) {
  return json_object_get_count(featureObject(remote, index));
}

const char *irRemoteFeatureValueName(const irRemote *remote, size_t index, size_t valueIndex) {
  return json_object_get_name(featureObject(remote, index), valueIndex);
}

int irRemoteHasFeature(const irRemote *remote, const char *name, const char *value) {
  size_t index;
  if (!irRemoteFeatureIndex(remote, name, &index))
    return 0;
  size_t count = irRemoteFeatureValueCount(remote, index);
  for (size_t i = 0; i < count; i++) {
    if (strcmp(value, irRemoteFeatureValueName(remote, index, i)) == 0)
      return 1;
  }
  return 0;
}

size_t irRemoteSymbolCount(const irRemote *remote) {
  return json_object_get_count(json_object_get_object(remote->root, "symboldefinitions"));
}

void irRemoteSymbols(const irRemote *remote, symbolDefinition symbols[]) {
  JSON_Object *definitions = json_object_get_object(remote->root, "symboldefinitions");
  if (!definitions) {
    log_error("Symbol definitions configuraiton not found");
    return;
  }
  size_t count = json_object_get_count(definitions);
  for (size_t i = 0; i < count; i++) {
    const char *symbol = json_object_get_name(definitions, i);
    JSON_Object *definition = json_object_get_object(definitions, symbol);
    symbols[i].symbol = symbol[0];
    symbols[i].markDuration = json_object_get_number(definition, "mark");
    symbols[i].spaceDuration = json_object_get_number(definition, "space");
  }
}

const char *irRemoteTemplate(const irRemote *remote) { return json_object_get_string(remote->root, "template"); }

const char *irRemoteDescription(const irRemote *remote) { return json_object_get_string(remote->root, "description"); }

const char *irRemoteDevice(const irRemote *remote) {
  return json_object_dotget_string(remote->root, "transmitter.device");
}

const char *irRemotePlugin(const irRemote *remote) { return json_object_get_string(remote->root, "plugin"); }

int irRemoteFrequency(const irRemote *remote) { return (int) json_object_get_number(remote->root, "frequency"); }

double irRemoteDutyCycle(const irRemote *remote) { return json_object_get_number(remote->root, "dutycycle"); }

unsigned int irRemoteOutPin(const irRemote *remote) {
  return (unsigned int) json_object_dotget_number(remote->root, "transmitter.outpin");
}

int irRemoteHasToggle(const irRemote *remote) {
  return json_object_get_count(json_object_get_object(remote->root, "toggle")) > 0;
}

int irRemoteHasVariants(const irRemote *remote) {
  return json_array_get_count(json_object_get_array(remote->root, "variants")) > 0;
}

size_t irRemoteMaxCodeLength(const irRemote *remote) {
  const char *text = json_object_get_string(remote->root, "template");
  size_t longest = text ? strlen(text) : 0;
  JSON_Array *variants = json_object_get_array(remote->root, "variants");
  for (size_t i = 0; i < json_array_get_count(variants); i++) {
    text = json_object_get_string(json_array_get_object(variants, i), "template");
    if (text && strlen(text) > longest)
      longest = strlen(text);
  }
  return longest;
}

const JSON_Array *irRemoteChecksums(const irRemote *remote) {
  return json_object_get_array(remote->selected ? remote->selected : remote->root, "checksums");
}

// Copy the symbols of an overlay to code, except spaces. A shorter overlay
// leaves the rest of the code as it is.
static void applyOverlay(const char *overlay, char *code, size_t codeLength) {
  size_t length = strlen(overlay);
  if (length > codeLength)
    log_warn("Feature code '%s' is longer than the template (%zu symbols)", overlay, codeLength);
  for (size_t i = 0; i < length && i < codeLength; i++) {
    if (overlay[i] != ' ')
      code[i] = overlay[i];
  }
}

// The requested value of a feature, NULL when it is not requested
static const char *requestedValue(const featureT *features, size_t count, const char *name) {
  const char *value = 0;
  for (size_t i = 0; i < count; i++) {
    if (features[i].name && features[i].value && strcmp(features[i].name, name) == 0)
      value = features[i].value;
  }
  return value;
}

// All features of a "when" object are requested with its values
static int whenMatches(JSON_Object *when, const featureT *features, size_t count) {
  for (size_t j = 0; j < json_object_get_count(when); j++) {
    const char *name = json_object_get_name(when, j);
    const char *wanted = json_object_get_string(when, name);
    const char *value = requestedValue(features, count, name);
    if (!wanted || !value || strcmp(wanted, value) != 0)
      return 0;
  }
  return 1;
}

// Apply the "overrides" of a definition whose "when" features are all
// requested with the given values, in order, after the features
static void applyOverrides(const irRemote *remote, JSON_Object *definition, const featureT *features, size_t count,
                           char *code, size_t codeLength) {
  JSON_Array *overrides = json_object_get_array(definition, "overrides");
  for (size_t i = 0; i < json_array_get_count(overrides); i++) {
    JSON_Object *override = json_array_get_object(overrides, i);
    JSON_Object *when = json_object_get_object(override, "when");
    const char *overlay = json_object_get_string(override, "code");
    if (!when || !overlay) {
      log_error("Override %zu in %s needs \"when\" and \"code\"", i, remote->name);
      continue;
    }
    if (whenMatches(when, features, count))
      applyOverlay(overlay, code, codeLength);
  }
}

// The first of the "variants" whose "when" features are all requested, or
// the remote itself
static JSON_Object *selectDefinition(const irRemote *remote, const featureT *features, size_t count) {
  JSON_Array *variants = json_object_get_array(remote->root, "variants");
  for (size_t i = 0; features && i < json_array_get_count(variants); i++) {
    JSON_Object *variant = json_array_get_object(variants, i);
    JSON_Object *when = json_object_get_object(variant, "when");
    if (!when || !json_object_get_string(variant, "template")) {
      log_error("Variant %zu in %s needs \"when\" and \"template\"", i, remote->name);
      continue;
    }
    if (whenMatches(when, features, count))
      return variant;
  }
  return remote->root;
}

int irRemoteEncode(irRemote *remote, const featureT *features, int toggled, char *code, size_t size) {
  // Requested features are stored at the index of the remote's features
  size_t requestedCount = irRemoteFeatureCount(remote);
  JSON_Object *definition = selectDefinition(remote, features, requestedCount);
  remote->selected = definition;

  const char *templateCode = json_object_get_string(definition, "template");
  if (!templateCode) {
    log_error("JSON file %s has no template", remote->name);
    templateCode = "";
  }
  size_t templateLength = strlen(templateCode);
  if (templateLength >= size) {
    log_error("Code of %s needs %zu symbols, room for %zu", remote->name, templateLength, size ? size - 1 : 0);
    return 1;
  }
  // The template fits, checked above; memcpy_s (C11 Annex K) is in neither
  // glibc nor newlib
  // NOLINTNEXTLINE(clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling)
  memcpy(code, templateCode, templateLength + 1);
  if (!features)
    return 0;

  // A variant has its own features, if any: their codes refer to its template
  JSON_Object *featureDefinitions =
      definition == remote->root ? featuresObject(remote) : json_object_get_object(definition, "features");
  size_t featuresCount = json_object_get_count(featureDefinitions);
  for (size_t configIndex = 0; configIndex < featuresCount; configIndex++) {
    const char *featureName = json_object_get_name(featureDefinitions, configIndex);
    const char *featureValue = requestedValue(features, requestedCount, featureName);
    if (!featureValue)
      continue;

    JSON_Object *featureObject = json_object_get_object(featureDefinitions, featureName);
    const char *featureString = json_object_get_string(featureObject, featureValue);
    if (featureString && toggled && definition == remote->root) {
      JSON_Object *toggleObject = json_object_get_object(json_object_get_object(remote->root, "toggle"), featureName);
      const char *toggleString = json_object_get_string(toggleObject, featureValue);
      if (toggleString)
        featureString = toggleString;
    }
    if (!featureString) {
      log_error("Feature '%s'='%s' not found in %s", featureName, featureValue, remote->name);
      continue;
    }
    applyOverlay(featureString, code, templateLength);
  }
  applyOverrides(remote, definition, features, requestedCount, code, templateLength);
  return 0;
}
