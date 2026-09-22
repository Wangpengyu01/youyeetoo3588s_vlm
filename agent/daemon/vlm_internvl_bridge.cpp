// P5b: InternVL3 six-tuple in-process bridge (from rknn3-model-zoo InternVLM/cpp/main.cc).
#include "vlm_internvl_bridge.h"

#include "Tokenizer.h"
#include "float16.h"
#include "image_utils.h"
#include "internvl3.h"
#include "time_utils.h"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <string>

const rknn3_sampling_params SAMPLE_PARAMS = {
    .top_k = 1,
    .top_p = 0.9f,
    .temperature = 1.0f,
    .repeat_penalty = 1.0f,
    .frequency_penalty = 0.0f,
    .presence_penalty = 0.0f,
};

const char *system_prompt =
    "<|im_start|>system\nYou are a helpful assistant.\n";
const char *prompt_prefix = "<|im_start|>user\n";
const char *prompt_postfix = "\n<|im_start|>assistant\n";

namespace {

struct embedding_info {
  int fd = -1;
  float16 *embedding_data = nullptr;
  int embedding_dim = 0;
  int vocab_size = 0;
};

rknn_app_context_t g_app;
Tokenizer *g_tokenizer = nullptr;
embedding_info g_embed;
struct stat g_emb_st {};
float16 *g_img_embeds = nullptr;
size_t g_embed_elems = 0;
bool g_ready = false;

void (*g_on_token)(const char *piece, void *userdata) = nullptr;
void *g_on_token_ud = nullptr;

int result_callback(void *userdata, RKLLMResult *result, LLMCallState state)
{
  Tokenizer *tokenizer = (Tokenizer *)userdata;
  if (state == RKLLM_RUN_ERROR || state == RKLLM_RUN_FINISH || state == RKLLM_RUN_MAX_NEW_TOKEN_REACHED ||
      state == RKLLM_RUN_STOP || state == RKLLM_RUN_WAITING)
    return 0;

  if (state == RKLLM_RUN_NORMAL && g_on_token)
  {
    std::string piece;
    if (result->num_tokens == 1)
      piece = tokenizer->TokenToPiece(result->token_ids[0]);
    else
      piece = tokenizer->Decode(result->token_ids, result->num_tokens);
    if (!piece.empty())
      g_on_token(piece.c_str(), g_on_token_ud);
  }
  return 0;
}

int tokenizer_callback(void *userdata, const char *text, int32_t text_len, int32_t *tokens, int32_t n_tokens_max)
{
  Tokenizer *tokenizer = (Tokenizer *)userdata;
  return tokenizer->Tokenize(text, text_len, tokens, n_tokens_max);
}

int embed_callback(void *userdata, int32_t *tokens, uint64_t num_tokens, void *embed, uint64_t len)
{
  auto *embed_info = (embedding_info *)userdata;
  if (len != num_tokens * (uint64_t)embed_info->embedding_dim * sizeof(float16))
    return -1;
  for (uint64_t n = 0; n < num_tokens; n++)
  {
    memcpy((unsigned char *)embed + n * embed_info->embedding_dim * sizeof(float16),
           embed_info->embedding_data + tokens[n] * embed_info->embedding_dim,
           embed_info->embedding_dim * sizeof(float16));
  }
  return 0;
}

int run_multimodal(const char *jpeg_path, const char *prompt, int max_new_tokens)
{
  if (!g_ready || !g_app.llm.rknn_sess)
    return -1;

  image_buffer_t src_image;
  memset(&src_image, 0, sizeof(src_image));
  if (read_image(jpeg_path, &src_image) != 0)
  {
    fprintf(stderr, "[vlm_internvl] read_image failed: %s\n", jpeg_path);
    return -1;
  }

  std::string prompt_with_image = std::string("<image> ") + prompt;
  rknn3_llm_multimodal_tensor tensor;
  memset(&tensor, 0, sizeof(tensor));
  tensor.name = "input_embeds";
  tensor.prompt = prompt_with_image.c_str();
  tensor.image.image_embed = g_img_embeds;
  tensor.image.n_image_tokens = g_app.vision.embeds_shape[1];
  tensor.image.n_image = g_app.vision.embeds_shape[0];
  tensor.image.image_width = g_app.vision.model_width;
  tensor.image.image_height = g_app.vision.model_height;
  tensor.image.image_start = "<img>";
  tensor.image.image_end = "</img>";
  tensor.image.image_content = "<IMG_CONTEXT>";
  tensor.enable_thinking = false;

  rknn_perf_metrics_t perf;
  memset(&perf, 0, sizeof(perf));

  // Override max tokens for this run via session infer param inside inference_internvl3_llm (uses MAX_NEW_TOKENS).
  // Demo sets keep_history=0 per shot; acceptable for see().
  int ret = inference_internvl3_model(&g_app, &src_image, g_img_embeds, tensor, 1, &perf);
  if (src_image.virt_addr)
    free(src_image.virt_addr);
  (void)max_new_tokens;
  return ret;
}

} // namespace

extern "C" {

int vlm_internvl_init(const struct vlm_internvl_config *cfg)
{
  if (!cfg || g_ready)
    return -1;

  memset(&g_app, 0, sizeof(g_app));
  memset(&g_embed, 0, sizeof(g_embed));
  memset(&g_emb_st, 0, sizeof(g_emb_st));

  fprintf(stderr, "[vlm_internvl] loading tokenizer…\n");
  fflush(stderr);
  g_tokenizer = new Tokenizer(TOKENIZER_BACKEND_LLAMA, cfg->tokenizer_path);
  if (!g_tokenizer)
    return -1;

  VocabInfo vocab_info;
  g_tokenizer->GetVocabInfo(&vocab_info);
  fprintf(stderr, "[vlm_internvl] tokenizer ok — loading vision+llm on 1828 (often 2–8 min, log may pause)…\n");
  fflush(stderr);

  g_embed.fd = open(cfg->embed_path, O_RDONLY);
  if (g_embed.fd < 0)
  {
    vlm_internvl_deinit();
    return -1;
  }
  if (fstat(g_embed.fd, &g_emb_st) != 0)
  {
    vlm_internvl_deinit();
    return -1;
  }
  g_embed.embedding_data =
      (float16 *)mmap(NULL, g_emb_st.st_size, PROT_READ, MAP_PRIVATE, g_embed.fd, 0);
  if (g_embed.embedding_data == MAP_FAILED)
  {
    vlm_internvl_deinit();
    return -1;
  }
  g_embed.vocab_size = vocab_info.vocab_size;
  g_embed.embedding_dim = (int)((g_emb_st.st_size / vocab_info.vocab_size) / sizeof(float16));

  rknn3_llm_param params;
  memset(&params, 0, sizeof(params));
  params.logits_name = (char *)"logits";
  params.max_context_len = cfg->max_context_len > 0 ? cfg->max_context_len : MAX_CONTEXT_LEN;
  params.sampling_param = SAMPLE_PARAMS;
  params.vocab_info.vocab_size = vocab_info.vocab_size;
  params.vocab_info.n_special_eos_id = vocab_info.n_special_eos_id;
  params.vocab_info.n_special_bos_id = vocab_info.n_special_bos_id;
  memcpy(params.vocab_info.special_eos_id, vocab_info.special_eos_id, sizeof(vocab_info.special_eos_id));
  memcpy(params.vocab_info.special_bos_id, vocab_info.special_bos_id, sizeof(vocab_info.special_bos_id));
  params.vocab_info.linefeed_id = vocab_info.linefeed_id;

  RKLLMCallback callback;
  memset(&callback, 0, sizeof(callback));
  callback.result_callback = result_callback;
  callback.result_userdata = g_tokenizer;
  callback.tokenizer_callback = tokenizer_callback;
  callback.tokenizer_userdata = g_tokenizer;
  callback.embed_callback = embed_callback;
  callback.embed_userdata = &g_embed;

  int ret = init_internvl3_model(&g_app, cfg->llm_rknn, cfg->llm_weight, cfg->vision_rknn, cfg->vision_weight, &params,
                                 1, callback, cfg->vision_core_mask, cfg->llm_core_mask);
  if (ret != 0)
  {
    fprintf(stderr, "[vlm_internvl] init_internvl3_model ret=%d\n", ret);
    vlm_internvl_deinit();
    return -1;
  }

  g_embed_elems = 1;
  for (size_t i = 0; i < g_app.vision.embeds_ndims; i++)
    g_embed_elems *= g_app.vision.embeds_shape[i];
  g_img_embeds = (float16 *)malloc(g_embed_elems * sizeof(float16));
  if (!g_img_embeds)
  {
    vlm_internvl_deinit();
    return -1;
  }

  g_ready = true;
  fprintf(stderr, "[vlm_internvl] six-tuple ready ctx=%d\n", params.max_context_len);
  return 0;
}

void vlm_internvl_deinit(void)
{
  if (g_ready)
  {
    release_internvl3_model(&g_app);
    g_ready = false;
  }
  if (g_img_embeds)
  {
    free(g_img_embeds);
    g_img_embeds = nullptr;
  }
  if (g_embed.fd >= 0)
  {
    if (g_embed.embedding_data && g_embed.embedding_data != MAP_FAILED)
      munmap(g_embed.embedding_data, g_emb_st.st_size);
    close(g_embed.fd);
    g_embed = embedding_info{};
    g_emb_st = {};
  }
  if (g_tokenizer)
  {
    delete g_tokenizer;
    g_tokenizer = nullptr;
  }
  memset(&g_app, 0, sizeof(g_app));
}

int vlm_internvl_chat(const char *prompt, int max_new_tokens, void (*on_token)(const char *piece, void *userdata),
                      void *userdata)
{
  if (!g_ready || !prompt || !g_app.llm.rknn_sess)
    return -1;

  g_on_token = on_token;
  g_on_token_ud = userdata;

  rknn3_llm_input inputs[1];
  rknn3_llm_infer_param infer_param;
  memset(&inputs, 0, sizeof(inputs));
  memset(&infer_param, 0, sizeof(infer_param));
  infer_param.keep_history = 1;
  infer_param.max_new_tokens = max_new_tokens > 0 ? max_new_tokens : 64;

  rknn3_llm_tensor tensor = {};
  tensor.prompt = prompt;
  tensor.enable_thinking = false;
  inputs[0].input_type = RKNN3_LLM_INPUT_PROMPT;
  inputs[0].llm_input = tensor;

  int ret = rknn3_session_run(g_app.llm.rknn_sess, inputs, 1, &infer_param);
  if (ret != RKNN3_SUCCESS)
    fprintf(stderr, "[vlm_internvl] chat session_run ret=%d\n", ret);
  return ret == RKNN3_SUCCESS ? 0 : -1;
}

int vlm_internvl_see(const char *jpeg_path, const char *prompt, int max_new_tokens,
                     void (*on_token)(const char *piece, void *userdata), void *userdata)
{
  if (!jpeg_path || !prompt)
    return -1;
  g_on_token = on_token;
  g_on_token_ud = userdata;
  return run_multimodal(jpeg_path, prompt, max_new_tokens);
}

} // extern "C"
