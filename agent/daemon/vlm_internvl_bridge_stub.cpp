// Stub until linked with rknn_internvl3_demo sources on SDK build host (see BUILD_VLM_DAEMON_P5b.md).
#include "vlm_internvl_bridge.h"

#include <stdio.h>

static int not_impl(const char *fn) {
  fprintf(stderr, "[vlm_internvl] %s: rebuild with SDK InternVL demo sources (P5b)\n", fn);
  return -1;
}

int vlm_internvl_init(const struct vlm_internvl_config *cfg) {
  (void)cfg;
  return not_impl("init");
}

void vlm_internvl_deinit(void) {}

int vlm_internvl_chat(
    const char *prompt,
    int max_new_tokens,
    void (*on_token)(const char *piece, void *userdata),
    void *userdata) {
  (void)prompt;
  (void)max_new_tokens;
  (void)on_token;
  (void)userdata;
  return not_impl("chat");
}

int vlm_internvl_see(
    const char *jpeg_path,
    const char *prompt,
    int max_new_tokens,
    void (*on_token)(const char *piece, void *userdata),
    void *userdata) {
  (void)jpeg_path;
  (void)prompt;
  (void)max_new_tokens;
  (void)on_token;
  (void)userdata;
  return not_impl("see");
}
