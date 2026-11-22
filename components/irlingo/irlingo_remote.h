// ESPHome glue: an irlingo remote sent through a remote_transmitter. The
// remote is encoded by irlingo's portable C code in this directory.
#pragma once

#include <memory>
#include <string>
#include <utility>
#include <vector>

#include "esphome/components/remote_transmitter/remote_transmitter.h"
#include "esphome/core/automation.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

extern "C" {
#include "irremote.h"
}

namespace esphome::irlingo {

class IrlingoRemote : public Component {
 public:
  void set_transmitter(remote_transmitter::RemoteTransmitterComponent *transmitter) {
    this->transmitter_ = transmitter;
  }
  void set_remote(const char *json) { this->json_ = json; }
  void set_name(const char *name) { this->name_ = name; }

  /// Parses the remote once and allocates the buffers sending needs, so
  /// send() allocates nothing
  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::DATA; }

  /// Send the code for these feature values (count of them), as
  /// `irlingo --remote ... --feature name=value` does. Features not given keep the
  /// remote's template. The code is sent send_times times, with send_wait
  /// microseconds between them. Returns false on errors (logged).
  bool send(const featureT *features, size_t count, uint32_t send_times = 1, uint32_t send_wait = 0);

 protected:
  remote_transmitter::RemoteTransmitterComponent *transmitter_{nullptr};
  const char *json_{nullptr};
  const char *name_{""};
  irRemote *remote_{nullptr};
  // Buffers for send(), sized for this remote in setup()
  size_t feature_count_{0};
  std::unique_ptr<featureT[]> requested_;
  size_t code_size_{0};
  std::unique_ptr<char[]> code_;
  std::unique_ptr<size_t[]> bit_pos_;
  size_t symbol_count_{0};
  std::unique_ptr<symbolDefinition[]> symbols_;
  std::unique_ptr<unsigned int[]> pulses_;
  int frequency_{38000};
  bool has_toggle_{false};
  bool toggled_{false};
  ESPPreferenceObject toggle_pref_;
};

template<typename... Ts> class SendAction : public Action<Ts...>, public Parented<IrlingoRemote> {
 public:
  template<typename V> void add_feature(const char *name, V value) {
    this->templates_.emplace_back(value);
    this->values_.emplace_back();
    this->features_.push_back(featureT{name, nullptr});
  }

  void set_send_times(uint32_t send_times) { this->send_times_ = send_times; }
  void set_send_wait(uint32_t send_wait) { this->send_wait_ = send_wait; }

  void play(const Ts &...x) override {
    // Feature values are short, so assigning them fits the strings' own
    // storage instead of allocating
    for (size_t i = 0; i < this->templates_.size(); i++) {
      this->values_[i] = this->templates_[i].value(x...);
      this->features_[i].value = this->values_[i].c_str();
    }
    this->parent_->send(this->features_.data(), this->features_.size(), this->send_times_, this->send_wait_);
  }

 protected:
  std::vector<TemplatableValue<std::string, Ts...>> templates_;
  std::vector<std::string> values_;
  std::vector<featureT> features_;
  uint32_t send_times_{1};
  uint32_t send_wait_{0};
};

}  // namespace esphome::irlingo
