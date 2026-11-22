#include "irlingo_remote.h"

#include <algorithm>
#include <cstring>

#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

extern "C" {
#include "checksum.h"
#include "plugins.h"
#include "pulses.h"
}

namespace esphome::irlingo {

static const char *const TAG = "irlingo";

void IrlingoRemote::setup() {
  this->remote_ = irRemoteParse(this->json_, this->name_);
  if (this->remote_ == nullptr) {
    ESP_LOGE(TAG, "Remote %s cannot be loaded", this->name_);
    this->mark_failed();
    return;
  }

  // Every code of this remote fits these buffers: a code is as long as the
  // longest template, and has at most two pulses or spaces per symbol
  this->feature_count_ = irRemoteFeatureCount(this->remote_);
  this->requested_ = std::make_unique<featureT[]>(std::max<size_t>(this->feature_count_, 1));
  size_t length = irRemoteMaxCodeLength(this->remote_);
  this->code_size_ = length + 1;
  this->code_ = std::make_unique<char[]>(this->code_size_);
  this->bit_pos_ = std::make_unique<size_t[]>(this->code_size_);
  this->pulses_ = std::make_unique<unsigned int[]>(std::min<size_t>(2 * length + 1, MAX_PULSE_VALUES));
  this->symbol_count_ = irRemoteSymbolCount(this->remote_);
  this->symbols_ = std::make_unique<symbolDefinition[]>(std::max<size_t>(this->symbol_count_, 1));
  irRemoteSymbols(this->remote_, this->symbols_.get());
  this->frequency_ = irRemoteFrequency(this->remote_);

  // Remotes with a toggle bit send a different code on every other press;
  // remember which one is next across restarts
  this->has_toggle_ = irRemoteHasToggle(this->remote_);
  if (this->has_toggle_) {
    this->toggle_pref_ =
        global_preferences->make_preference<bool>(fnv1_hash_extend(fnv1_hash("irlingo_"), this->name_));
    this->toggle_pref_.load(&this->toggled_);
  }
}

void IrlingoRemote::dump_config() {
  ESP_LOGCONFIG(TAG, "irlingo remote %s:", this->name_);
  ESP_LOGCONFIG(TAG, "  Size: %u bytes", (unsigned) strlen(this->json_));
  ESP_LOGCONFIG(TAG, "  Longest code: %u symbols", (unsigned) (this->code_size_ ? this->code_size_ - 1 : 0));
  ESP_LOGCONFIG(TAG, "  Toggle bit: %s", YESNO(this->has_toggle_));
}

bool IrlingoRemote::send(const featureT *features, size_t count, uint32_t send_times, uint32_t send_wait) {
  if (this->remote_ == nullptr) {
    ESP_LOGE(TAG, "Remote %s cannot be loaded", this->name_);
    return false;
  }

  // The requested values, at the index of their feature in the remote
  for (size_t i = 0; i < this->feature_count_; i++)
    this->requested_[i] = featureT{nullptr, nullptr};
  for (size_t i = 0; i < count; i++) {
    size_t index;
    if (!irRemoteHasFeature(this->remote_, features[i].name, features[i].value) ||
        !irRemoteFeatureIndex(this->remote_, features[i].name, &index)) {
      ESP_LOGE(TAG, "Remote %s has no feature %s=%s", this->name_, features[i].name, features[i].value);
      return false;
    }
    this->requested_[index] = features[i];
  }

  // The same steps as the irlingo command: features (with overrides and
  // variants), checksums, plugin, then pulses
  char *code = this->code_.get();
  if (irRemoteEncode(this->remote_, this->requested_.get(), this->toggled_ ? 1 : 0, code, this->code_size_))
    return false;
  if (applyChecksums(irRemoteChecksums(this->remote_), code, this->bit_pos_.get())) {
    ESP_LOGE(TAG, "Remote %s has an invalid checksum", this->name_);
    return false;
  }
  const char *plugin = irRemotePlugin(this->remote_);
  if (applyRemotePlugin(plugin, code)) {
    ESP_LOGE(TAG, "Remote %s needs the unknown plugin %s", this->name_, plugin);
    return false;
  }
  ESP_LOGD(TAG, "%s: %s", this->name_, code);
  size_t pulse_count = 0;
  if (irlingoBuildPulses(this->symbol_count_, this->symbols_.get(), code, this->pulses_.get(), &pulse_count))
    return false;

  auto call = this->transmitter_->transmit();
  auto *data = call.get_data();
  data->set_carrier_frequency(this->frequency_);
  data->reserve(pulse_count);
  for (size_t i = 0; i < pulse_count; i++) {
    if (i % 2 == 0) {
      data->mark(this->pulses_[i]);
    } else {
      data->space(this->pulses_[i]);
    }
  }
  call.set_send_times(send_times);
  call.set_send_wait(send_wait);
  call.perform();
  ESP_LOGI(TAG, "Sent %s (%u pulses and spaces at %d Hz, %u times)", this->name_, (unsigned) pulse_count,
           this->frequency_, (unsigned) send_times);

  if (this->has_toggle_) {
    this->toggled_ = !this->toggled_;
    this->toggle_pref_.save(&this->toggled_);
  }
  return true;
}

}  // namespace esphome::irlingo
