// P5b: InternVL3.5 six-tuple inference bridge (implemented in SDK build tree, stub on host).
#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct vlm_internvl_config {
  const char *vision_rknn;
  const char *vision_weight;
  const char *llm_rknn;
  const char *llm_weight;
  const char *tokenizer_path;
  const char *embed_path;
  uint32_t llm_core_mask;
  uint32_t vision_core_mask;
  int32_t max_context_len;
};

/** Load vision + LLM (six files). Returns 0 on success. */
int vlm_internvl_init(const struct vlm_internvl_config *cfg);

void vlm_internvl_deinit(void);

/** Text-only chat (M2: must skip vision encoder when implemented). */
int vlm_internvl_chat(
    const char *prompt,
    int max_new_tokens,
    void (*on_token)(const char *piece, void *userdata),
    void *userdata);

/** JPEG path + prompt; runs vision prefill + decode. */
int vlm_internvl_see(
    const char *jpeg_path,
    const char *prompt,
    int max_new_tokens,
    void (*on_token)(const char *piece, void *userdata),
    void *userdata);

#ifdef __cplusplus
}
#endif
