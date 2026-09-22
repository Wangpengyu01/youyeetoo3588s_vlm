// vlm_daemon — P5b M1: LLM session + JSONL socket; --cli for shell UX; see via vlm_cli_see.sh bridge until six-tuple in-process (M2).
// Fork baseline: agent/daemon/llm_daemon.cpp · RKNN3 1.0.5b10

#include "Tokenizer.h"
#include "float16.h"
#include "rknn3_api.h"
#include "vlm_internvl_bridge.h"

#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/un.h>
#include <unistd.h>

#include <string>
#include <vector>

#define LOGW(fmt, ...) fprintf(stderr, "\033[33m" fmt "\033[0m", ##__VA_ARGS__)
#define DEFAULT_SOCK "/tmp/r1-vlm.sock"
#define VLM_CLI_SEE "/userdata/agent/scripts/vlm_cli_see.sh"

static rknn3_context g_ctx = 0;
static rknn3_session *g_session = nullptr;
static Tokenizer *g_tokenizer = nullptr;
static struct embedding_info
{
  int fd;
  float16 *embedding_data;
  size_t mmap_size;
  int embedding_dim;
  int vocab_size;
} g_embed;

static int g_client_fd = -1;
static std::string g_req_id;
static struct timeval g_start, g_first_token, g_end;
static bool g_first_decode = true;
static pthread_mutex_t g_infer_mu = PTHREAD_MUTEX_INITIALIZER;
static char g_sock_path[108] = DEFAULT_SOCK;
static volatile sig_atomic_t g_stop = 0;
static bool g_cli_stdout = false;
static std::string g_path_model;
static std::string g_path_weight;
static std::string g_path_tok;
static std::string g_path_embed;
static int32_t g_max_ctx = 1024;
static uint32_t g_core_mask = 0xff;
static bool g_p5b_internvl = false;
static std::string g_path_vis_model;
static std::string g_path_vis_weight;
static uint32_t g_vision_core_mask = 0xff;

static void json_escape_append(const char *s, std::string &out)
{
  for (const unsigned char *p = (const unsigned char *)s; *p; ++p)
  {
    char c = (char)*p;
    if (c == '\\' || c == '"')
    {
      out.push_back('\\');
      out.push_back(c);
    }
    else if (c == '\n')
    {
      out.append("\\n");
    }
    else if (c == '\r')
    {
      out.append("\\r");
    }
    else if (c == '\t')
    {
      out.append("\\t");
    }
    else
    {
      out.push_back(c);
    }
  }
}

static bool send_line(int fd, const std::string &line)
{
  std::string msg = line;
  msg.push_back('\n');
  const char *p = msg.c_str();
  size_t left = msg.size();
  while (left > 0)
  {
    ssize_t n = send(fd, p, left, MSG_NOSIGNAL);
    if (n <= 0)
      return false;
    p += n;
    left -= (size_t)n;
  }
  return true;
}

static void send_error(int fd, const char *id, const char *message)
{
  std::string line = "{\"type\":\"error\",\"id\":\"";
  line += (id ? id : "");
  line += "\",\"message\":\"";
  json_escape_append(message, line);
  line += "\"}";
  send_line(fd, line);
}

static void internvl_token_cb(const char *piece, void *)
{
  if (!piece || !piece[0])
    return;
  int fd = g_client_fd;
  if (g_cli_stdout)
  {
    fputs(piece, stdout);
    fflush(stdout);
    return;
  }
  if (fd < 0)
    return;
  if (g_first_decode)
  {
    gettimeofday(&g_first_token, NULL);
    g_first_decode = false;
  }
  std::string line = "{\"type\":\"token\",\"id\":\"";
  line += g_req_id;
  line += "\",\"text\":\"";
  json_escape_append(piece, line);
  line += "\"}";
  send_line(fd, line);
}

static bool json_get_string(const std::string &json, const char *key, std::string &out)
{
  std::string needle = std::string("\"") + key + "\":";
  size_t pos = json.find(needle);
  if (pos == std::string::npos)
    return false;
  pos += needle.size();
  while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t'))
    ++pos;
  if (pos >= json.size() || json[pos] != '"')
    return false;
  ++pos;
  out.clear();
  for (size_t i = pos; i < json.size(); ++i)
  {
    char c = json[i];
    if (c == '\\' && i + 1 < json.size())
    {
      char n = json[++i];
      if (n == 'n')
        out.push_back('\n');
      else if (n == 'r')
        out.push_back('\r');
      else if (n == 't')
        out.push_back('\t');
      else
        out.push_back(n);
      continue;
    }
    if (c == '"')
      return true;
    out.push_back(c);
  }
  return false;
}

static int json_get_int(const std::string &json, const char *key, int fallback)
{
  std::string needle = std::string("\"") + key + "\":";
  size_t pos = json.find(needle);
  if (pos == std::string::npos)
    return fallback;
  pos += needle.size();
  while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t'))
    ++pos;
  return atoi(json.c_str() + pos);
}

static int tokenizer_callback(void *userdata, const char *text, int32_t text_len, int32_t *tokens, int32_t n_tokens_max)
{
  Tokenizer *tokenizer = (Tokenizer *)userdata;
  int n_tokens = tokenizer->Tokenize(text, text_len, tokens, n_tokens_max);
  if (n_tokens <= 0)
    fprintf(stderr, "tokenizer failed\n");
  return n_tokens;
}

static int embed_callback(void *userdata, int32_t *tokens, uint64_t num_tokens, void *embed, uint64_t len)
{
  struct embedding_info *info = (struct embedding_info *)userdata;
  if (len != num_tokens * info->embedding_dim * sizeof(float16))
    return -1;
  for (uint64_t n = 0; n < num_tokens; ++n)
  {
    memcpy((unsigned char *)embed + n * info->embedding_dim * sizeof(float16),
           info->embedding_data + tokens[n] * info->embedding_dim,
           info->embedding_dim * sizeof(float16));
  }
  return 0;
}

static int result_callback(void *userdata, RKLLMResult *result, LLMCallState state)
{
  Tokenizer *tokenizer = (Tokenizer *)userdata;
  int fd = g_client_fd;
  if (fd < 0)
    return 0;

  if (state == RKLLM_RUN_ERROR)
  {
    if (fd >= 0)
      send_error(fd, g_req_id.c_str(), "inference error");
    else
      fprintf(stderr, "\n[cli] inference error\n");
    return 0;
  }
  if (state == RKLLM_RUN_NORMAL)
  {
    std::string piece;
    if (result->num_tokens == 1)
      piece = tokenizer->TokenToPiece(result->token_ids[0]);
    else
      piece = tokenizer->Decode(result->token_ids, result->num_tokens);

    if (g_first_decode)
    {
      gettimeofday(&g_first_token, NULL);
      g_first_decode = false;
    }

    if (g_cli_stdout)
    {
      fputs(piece.c_str(), stdout);
      fflush(stdout);
    }
    else
    {
      std::string line = "{\"type\":\"token\",\"id\":\"";
      line += g_req_id;
      line += "\",\"text\":\"";
      json_escape_append(piece.c_str(), line);
      line += "\"}";
      send_line(fd, line);
    }
  }
  return 0;
}

static int init_context_and_model(rknn3_context *p_ctx, const char *model_path, const char *weight_path,
                                  uint32_t core_mask, const char *key_path, const char *device_id)
{
  rknn3_config config;
  rknn3_context ctx = 0;
  rknn3_init_extend init_extend = {0};
  init_extend.device_id = (char *)device_id;
  int ret = rknn3_init(&ctx, &init_extend);
  if (ret < 0)
    return ret;

  if (key_path != nullptr && strlen(key_path) > 0)
  {
    ret = rknn3_set_decrypt_key_from_path(ctx, key_path);
    if (ret != RKNN3_SUCCESS)
    {
      rknn3_destroy(ctx);
      return -1;
    }
  }

  ret = rknn3_load_model_from_path(ctx, model_path, weight_path);
  if (ret != RKNN3_SUCCESS)
  {
    rknn3_destroy(ctx);
    return -1;
  }

  memset(&config, 0, sizeof(config));
  config.run_core_mask = core_mask;
  ret = rknn3_model_init(ctx, &config);
  if (ret != RKNN3_SUCCESS)
  {
    rknn3_destroy(ctx);
    return -1;
  }
  *p_ctx = ctx;
  return 0;
}

static int get_tokenizer_and_embedding(const char *tokenizer_path, VocabInfo *vocab_info, Tokenizer **tokenizer,
                                       struct embedding_info *embedding_info, const char *embedding_path,
                                       struct stat *emb_st)
{
  *tokenizer = new Tokenizer(TOKENIZER_BACKEND_LLAMA, tokenizer_path);
  (*tokenizer)->GetVocabInfo(vocab_info);
  memset(embedding_info, 0, sizeof(*embedding_info));
  embedding_info->fd = open(embedding_path, O_RDONLY);
  if (embedding_info->fd == -1)
    return -1;
  if (fstat(embedding_info->fd, emb_st) == -1)
    return -1;
  embedding_info->mmap_size = (size_t)emb_st->st_size;
  embedding_info->embedding_data =
      (float16 *)mmap(NULL, emb_st->st_size, PROT_READ, MAP_PRIVATE, embedding_info->fd, 0);
  if (embedding_info->embedding_data == MAP_FAILED)
    return -1;
  embedding_info->vocab_size = vocab_info->vocab_size;
  embedding_info->embedding_dim = (emb_st->st_size / vocab_info->vocab_size) / sizeof(float16);
  return 0;
}

static int init_daemon(const char *model_path, const char *weight_path, const char *tokenizer_path,
                       const char *embedding_path, int32_t max_context_len, uint32_t core_mask)
{
  rknn3_devices devs;
  VocabInfo vocab_info;
  struct stat emb_st;
  RKLLMCallback callback;
  rknn3_llm_param params;
  rknn3_llm_config llm_config;
  memset(&devs, 0, sizeof(devs));
  memset(&vocab_info, 0, sizeof(vocab_info));
  memset(&g_embed, 0, sizeof(g_embed));
  memset(&callback, 0, sizeof(callback));
  memset(&params, 0, sizeof(params));
  memset(&llm_config, 0, sizeof(llm_config));

  int ret = rknn3_find_devices(&devs);
  if (ret != RKNN3_SUCCESS || devs.n_devices == 0)
    return -1;
  const char *device_id = devs.devices[0].id;
  fprintf(stderr, "[daemon] device=%s\n", device_id);

  ret = init_context_and_model(&g_ctx, model_path, weight_path, core_mask, nullptr, device_id);
  if (ret < 0)
    return ret;

  ret = get_tokenizer_and_embedding(tokenizer_path, &vocab_info, &g_tokenizer, &g_embed, embedding_path, &emb_st);
  if (ret < 0)
    return ret;

  ret = rknn3_query(g_ctx, RKNN3_QUERY_LLM_CONFIG, &llm_config, sizeof(llm_config));
  if (ret != RKNN3_SUCCESS)
    return ret;

  params.logits_name = (char *)"output";
  params.max_context_len = llm_config.max_ctx_len;
  params.sampling_param.temperature = 1.0f;
  params.sampling_param.top_k = 1;
  params.sampling_param.top_p = 0.9f;
  params.sampling_param.repeat_penalty = 1.1f;
  params.vocab_info.vocab_size = vocab_info.vocab_size;
  params.vocab_info.n_special_eos_id = vocab_info.n_special_eos_id;
  params.vocab_info.n_special_bos_id = vocab_info.n_special_bos_id;
  memcpy(params.vocab_info.special_eos_id, vocab_info.special_eos_id, sizeof(vocab_info.special_eos_id));
  memcpy(params.vocab_info.special_bos_id, vocab_info.special_bos_id, sizeof(vocab_info.special_bos_id));
  params.vocab_info.linefeed_id = vocab_info.linefeed_id;
  params.vocab_info.ignore_eos_token = 0;

  g_session = rknn3_session_init(g_ctx, &params, 1);
  if (!g_session)
    return -1;

  callback.result_callback = result_callback;
  callback.result_userdata = g_tokenizer;
  callback.embed_callback = embed_callback;
  callback.embed_userdata = &g_embed;
  callback.tokenizer_callback = tokenizer_callback;
  callback.tokenizer_userdata = g_tokenizer;
  ret = rknn3_session_set_callback(g_session, &callback);
  if (ret != RKNN3_SUCCESS)
    return ret;

  ret = rknn3_session_set_kvcache_policy(g_session, RKNN3_KVCACHE_POLICY_RECURRENT, nullptr);
  if (ret != RKNN3_SUCCESS)
    return ret;

  // Phase G-b (optional): enable InternVL ChatML so system_prompt is honored.
  // See agent/docs/BUILD_LINUX.md §9 — uncomment after editing template strings.
#if 0
  {
    const char *system_prompt =
        "<|im_start|>system\n你是 youyeetoo R1 语音助手小揽，只用简体中文简短回答。\n";
    const char *prompt_prefix = "<|im_start|>user\n";
    const char *prompt_postfix = "\n<|im_start|>assistant\n";
    ret = rknn3_session_set_chat_template(g_session, system_prompt, prompt_prefix, prompt_postfix);
    if (ret != RKNN3_SUCCESS)
    {
      fprintf(stderr, "[daemon] set_chat_template failed ret=%d\n", ret);
      return -1;
    }
    fprintf(stderr, "[daemon] chat template enabled (InternVL ChatML)\n");
  }
#endif

  if (max_context_len != llm_config.max_ctx_len && max_context_len > llm_config.max_ctx_len)
    return -1;

  fprintf(stderr, "[daemon] model ready ctx=%d type=%s\n", llm_config.max_ctx_len, llm_config.model_type);
  return 0;
}

static bool handle_chat(int fd, const std::string &line)
{
  std::string prompt;
  if (!json_get_string(line, "prompt", prompt) || prompt.empty())
  {
    send_error(fd, "", "missing prompt");
    return false;
  }
  std::string req_id;
  if (!json_get_string(line, "id", req_id))
    req_id = "req";
  int max_new = json_get_int(line, "max_new_tokens", 64);

  pthread_mutex_lock(&g_infer_mu);
  g_client_fd = fd;
  g_req_id = req_id;
  g_first_decode = true;
  gettimeofday(&g_start, NULL);

  int ret = RKNN3_SUCCESS;
  if (g_p5b_internvl)
  {
    ret = vlm_internvl_chat(prompt.c_str(), max_new, internvl_token_cb, nullptr);
  }
  else
  {
    rknn3_llm_infer_param infer_param = {.keep_history = 1, .max_new_tokens = max_new};
    rknn3_llm_input inputs[1];
    rknn3_llm_tensor tensor = {.name = NULL,
                               .prompt = prompt.c_str(),
                               .embed = NULL,
                               .tokens = NULL,
                               .n_tokens = 0,
                               .enable_thinking = false};
    rknn3_llm_input input = {.input_type = RKNN3_LLM_INPUT_PROMPT, .llm_input = tensor};
    inputs[0] = input;
    ret = rknn3_session_run(g_session, inputs, 1, &infer_param);
  }
  gettimeofday(&g_end, NULL);
  g_client_fd = -1;

  if (ret != RKNN3_SUCCESS)
  {
    pthread_mutex_unlock(&g_infer_mu);
    send_error(fd, req_id.c_str(), "rknn3_session_run failed");
    return false;
  }

  int decode_tokens = 0;
  if (!g_p5b_internvl && g_session)
  {
    RKLLMRunState state;
    memset(&state, 0, sizeof(state));
    rknn3_session_query_state(g_session, &state);
    decode_tokens = state.n_decode_tokens;
    if (state.n_total_tokens >= (state.n_max_tokens - max_new))
      rknn3_session_clear_kvcache(g_session, RKNN3_KVCACHE_CLEAR_ALL);
  }

  float prefill_ms = (g_first_token.tv_sec - g_start.tv_sec) * 1e3f + (g_first_token.tv_usec - g_start.tv_usec) / 1e3f;
  if (prefill_ms < 0)
    prefill_ms = 0;
  float total_ms = (g_end.tv_sec - g_start.tv_sec) * 1e3f + (g_end.tv_usec - g_start.tv_usec) / 1e3f;
  float generate_ms = total_ms - prefill_ms;
  if (generate_ms < 0)
    generate_ms = 0;

  char done[512];
  snprintf(done, sizeof(done),
           "{\"type\":\"done\",\"id\":\"%s\",\"usage\":{\"prefill_ms\":%.2f,\"generate_ms\":%.2f,\"tokens\":%d}}",
           req_id.c_str(), prefill_ms, generate_ms, decode_tokens);
  send_line(fd, done);
  pthread_mutex_unlock(&g_infer_mu);
  return true;
}

static void teardown_session()
{
  if (g_session)
  {
    rknn3_session_destroy(g_session);
    g_session = nullptr;
  }
  if (g_ctx)
  {
    rknn3_destroy(g_ctx);
    g_ctx = 0;
  }
  if (g_embed.embedding_data && g_embed.mmap_size)
  {
    munmap(g_embed.embedding_data, g_embed.mmap_size);
    g_embed.embedding_data = nullptr;
    g_embed.mmap_size = 0;
  }
  if (g_embed.fd != -1)
  {
    close(g_embed.fd);
    g_embed.fd = -1;
  }
  if (g_tokenizer)
  {
    delete g_tokenizer;
    g_tokenizer = nullptr;
  }
}

static bool vision_intent(const std::string &line)
{
  if (line.find("查看") != std::string::npos &&
      (line.find("画面") != std::string::npos || line.find("当前") != std::string::npos))
    return true;
  if (line.find("描述") != std::string::npos && line.find("画面") != std::string::npos)
    return true;
  if (line.find("看看") != std::string::npos || line.find("看一下") != std::string::npos ||
      line.find("看图") != std::string::npos)
    return true;
  return false;
}

static int run_see_infer(const std::string &image_path, const std::string &prompt, int max_new)
{
  if (g_p5b_internvl)
  {
    fprintf(stderr, "[vlm_daemon] P5b see in-process: %s\n", image_path.c_str());
    pthread_mutex_lock(&g_infer_mu);
    g_first_decode = true;
    gettimeofday(&g_start, NULL);
    int rc = vlm_internvl_see(image_path.c_str(), prompt.c_str(), max_new, internvl_token_cb, nullptr);
    gettimeofday(&g_end, NULL);
    pthread_mutex_unlock(&g_infer_mu);
    return rc;
  }
  setenv("VLM_SEE_PROMPT", prompt.c_str(), 1);
  std::string cmd = "bash ";
  cmd += VLM_CLI_SEE;
  cmd += " 2>/userdata/agent/logs/vlm_daemon_see.err";
  fprintf(stderr, "[vlm_daemon] M1 bridge see (external)…\n");
  pthread_mutex_lock(&g_infer_mu);
  teardown_session();
  pthread_mutex_unlock(&g_infer_mu);
  int rc = system(cmd.c_str());
  if (init_daemon(g_path_model.c_str(), g_path_weight.c_str(), g_path_tok.c_str(), g_path_embed.c_str(),
                  g_max_ctx, g_core_mask) != 0)
    return -1;
  return rc;
}

static bool handle_see(int fd, const std::string &line)
{
  std::string prompt;
  if (!json_get_string(line, "prompt", prompt) || prompt.empty())
    prompt = "用一句话描述当前画面。";
  std::string req_id;
  if (!json_get_string(line, "id", req_id))
    req_id = "see";
  std::string image_path;
  if (!json_get_string(line, "image_path", image_path) || image_path.empty())
    image_path = "/userdata/agent/run/camera_shot.jpg";
  int max_new = json_get_int(line, "max_new_tokens", 128);

  pthread_mutex_lock(&g_infer_mu);
  g_client_fd = fd;
  g_req_id = req_id;
  g_cli_stdout = false;
  pthread_mutex_unlock(&g_infer_mu);

  int rc = run_see_infer(image_path, prompt, max_new);
  g_client_fd = -1;

  if (rc != 0)
  {
    send_error(fd, req_id.c_str(), "see pipeline failed (vlm_cli_see.sh)");
    return false;
  }
  char done[256];
  snprintf(done, sizeof(done), "{\"type\":\"done\",\"id\":\"%s\",\"usage\":{\"see_ms\":0}}", req_id.c_str());
  send_line(fd, done);
  return true;
}

static void cli_loop()
{
  fprintf(stderr, "[vlm_daemon] interactive CLI (vision → %s)\n", VLM_CLI_SEE);
  fputs("小揽> ", stdout);
  fflush(stdout);
  char buf[4096];
  while (!g_stop && fgets(buf, sizeof(buf), stdin))
  {
    std::string line(buf);
    while (!line.empty() && (line.back() == '\n' || line.back() == '\r'))
      line.pop_back();
    if (line.empty())
    {
      fputs("小揽> ", stdout);
      fflush(stdout);
      continue;
    }
    if (line == "quit" || line == "exit" || line == "/quit")
      break;

    if (vision_intent(line))
    {
      fputs("\n", stdout);
      run_see_infer("/userdata/agent/run/camera_shot.jpg", line, 128);
      fputs("\n小揽> ", stdout);
      fflush(stdout);
      continue;
    }

    int fake_fd = -1;
    pthread_mutex_lock(&g_infer_mu);
    g_client_fd = fake_fd;
    g_req_id = "cli";
    g_cli_stdout = true;
    g_first_decode = true;
    gettimeofday(&g_start, NULL);

    rknn3_llm_infer_param infer_param = {.keep_history = 1, .max_new_tokens = 64};
    rknn3_llm_input inputs[1];
    rknn3_llm_tensor tensor = {.name = NULL,
                               .prompt = line.c_str(),
                               .embed = NULL,
                               .tokens = NULL,
                               .n_tokens = 0,
                               .enable_thinking = false};
    rknn3_llm_input input = {.input_type = RKNN3_LLM_INPUT_PROMPT, .llm_input = tensor};
    inputs[0] = input;
    int ret = RKNN3_SUCCESS;
    if (g_p5b_internvl)
      ret = vlm_internvl_chat(line.c_str(), 64, internvl_token_cb, nullptr);
    else
      ret = rknn3_session_run(g_session, inputs, 1, &infer_param);
    g_cli_stdout = false;
    g_client_fd = -1;
    pthread_mutex_unlock(&g_infer_mu);

    if (ret != RKNN3_SUCCESS)
      fprintf(stderr, "\n[cli] inference failed\n");
    else
      fputs("\n", stdout);
    fputs("小揽> ", stdout);
    fflush(stdout);
  }
}

static void handle_request(int fd, const std::string &line)
{
  if (line.find("\"type\":\"ping\"") != std::string::npos || line.find("\"type\": \"ping\"") != std::string::npos)
  {
    send_line(fd, "{\"type\":\"pong\"}");
    return;
  }
  if (line.find("clear_history") != std::string::npos)
  {
    pthread_mutex_lock(&g_infer_mu);
    if (g_session)
      rknn3_session_clear_kvcache(g_session, RKNN3_KVCACHE_CLEAR_ALL);
    pthread_mutex_unlock(&g_infer_mu);
    send_line(fd, "{\"type\":\"ok\",\"op\":\"clear_history\"}");
    return;
  }
  if (line.find("\"type\":\"chat\"") != std::string::npos || line.find("\"type\": \"chat\"") != std::string::npos)
  {
    handle_chat(fd, line);
    return;
  }
  if (line.find("\"type\":\"see\"") != std::string::npos || line.find("\"type\": \"see\"") != std::string::npos)
  {
    handle_see(fd, line);
    return;
  }
  send_error(fd, "", "unknown request type");
}

static void on_signal(int sig)
{
  (void)sig;
  g_stop = 1;
}

static int serve_forever()
{
  int srv = socket(AF_UNIX, SOCK_STREAM, 0);
  if (srv < 0)
    return -1;

  struct sockaddr_un addr;
  memset(&addr, 0, sizeof(addr));
  addr.sun_family = AF_UNIX;
  strncpy(addr.sun_path, g_sock_path, sizeof(addr.sun_path) - 1);
  unlink(g_sock_path);

  if (bind(srv, (struct sockaddr *)&addr, sizeof(addr)) < 0)
  {
    close(srv);
    return -1;
  }
  chmod(g_sock_path, 0777);
  if (listen(srv, 4) < 0)
  {
    close(srv);
    return -1;
  }
  fprintf(stderr, "[daemon] listening %s\n", g_sock_path);

  while (!g_stop)
  {
    struct pollfd pfd = {.fd = srv, .events = POLLIN};
    if (poll(&pfd, 1, 500) <= 0)
      continue;
    int cfd = accept(srv, NULL, NULL);
    if (cfd < 0)
      continue;

    std::string buf;
    char chunk[4096];
    while (true)
    {
      struct pollfd cf = {.fd = cfd, .events = POLLIN};
      if (poll(&cf, 1, 30000) <= 0)
        break;
      ssize_t n = recv(cfd, chunk, sizeof(chunk) - 1, 0);
      if (n <= 0)
        break;
      chunk[n] = '\0';
      buf.append(chunk, (size_t)n);
      size_t nl;
      while ((nl = buf.find('\n')) != std::string::npos)
      {
        std::string line = buf.substr(0, nl);
        buf.erase(0, nl + 1);
        if (!line.empty())
          handle_request(cfd, line);
      }
    }
    close(cfd);
  }

  close(srv);
  unlink(g_sock_path);
  return 0;
}

int main(int argc, char **argv)
{
  bool cli_mode = false;
  int base = 1;
  if (argc >= 2 && strcmp(argv[1], "--cli") == 0)
  {
    cli_mode = true;
    base = 2;
  }
  if (argc < base + 7)
  {
    LOGW("Usage (LLM-only M1): %s [--cli] <llm.rknn> <llm.weight> <tok> <embed> <ctx> <max_new> <core> [sock]\n",
         argv[0]);
    LOGW("Usage (P5b six-pack): %s [--cli] <vis.rknn> <vis.w> <llm.rknn> <llm.w> <tok> <embed> <ctx> <max_new> <vis_core> <llm_core> [sock]\n",
         argv[0]);
    return 1;
  }

  g_p5b_internvl = (argc >= base + 11);

  signal(SIGINT, on_signal);
  signal(SIGTERM, on_signal);
  if (g_p5b_internvl)
  {
    if (argc >= base + 12)
      strncpy(g_sock_path, argv[base + 11], sizeof(g_sock_path) - 1);
    g_path_vis_model = argv[base + 0];
    g_path_vis_weight = argv[base + 1];
    g_path_model = argv[base + 2];
    g_path_weight = argv[base + 3];
    g_path_tok = argv[base + 4];
    g_path_embed = argv[base + 5];
    g_max_ctx = atoi(argv[base + 6]);
    g_vision_core_mask = (uint32_t)strtoul(argv[base + 8], NULL, 16);
    g_core_mask = (uint32_t)strtoul(argv[base + 9], NULL, 16);
    struct vlm_internvl_config icfg = {
        .vision_rknn = g_path_vis_model.c_str(),
        .vision_weight = g_path_vis_weight.c_str(),
        .llm_rknn = g_path_model.c_str(),
        .llm_weight = g_path_weight.c_str(),
        .tokenizer_path = g_path_tok.c_str(),
        .embed_path = g_path_embed.c_str(),
        .llm_core_mask = g_core_mask,
        .vision_core_mask = g_vision_core_mask,
        .max_context_len = g_max_ctx,
    };
    if (vlm_internvl_init(&icfg) != 0)
    {
      fprintf(stderr, "[vlm_daemon] P5b internvl init failed\n");
      return 1;
    }
    fprintf(stderr, "[vlm_daemon] P5b six-tuple ready sock=%s\n", g_sock_path);
  }
  else
  {
    if (argc >= base + 8)
      strncpy(g_sock_path, argv[base + 7], sizeof(g_sock_path) - 1);
    g_path_model = argv[base + 0];
    g_path_weight = argv[base + 1];
    g_path_tok = argv[base + 2];
    g_path_embed = argv[base + 3];
    g_max_ctx = atoi(argv[base + 4]);
    g_core_mask = (uint32_t)strtoul(argv[base + 6], NULL, 16);
    if (init_daemon(g_path_model.c_str(), g_path_weight.c_str(), g_path_tok.c_str(), g_path_embed.c_str(), g_max_ctx,
                    g_core_mask) != 0)
    {
      fprintf(stderr, "[vlm_daemon] init failed\n");
      return 1;
    }
  }

  int rc = 0;
  if (cli_mode)
    cli_loop();
  else
    rc = serve_forever();

  if (g_p5b_internvl)
    vlm_internvl_deinit();
  else
  {
    pthread_mutex_lock(&g_infer_mu);
    teardown_session();
    pthread_mutex_unlock(&g_infer_mu);
  }

  return rc;
}
