#ifndef SYMBOLDEFINITION_H
#define SYMBOLDEFINITION_H

/// A symbol of a code and the pulse (mark) and space it is sent as, in
/// microseconds
typedef struct sd {
  char symbol;
  unsigned markDuration;
  unsigned spaceDuration;
} symbolDefinition;

#endif
