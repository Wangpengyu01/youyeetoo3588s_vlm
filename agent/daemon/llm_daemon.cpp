// llm_daemon — InternVL3.5-4B LLM-only persistent service (Ollama-style)
// Fork baseline: voice/src/rknn3_session_test.cpp · RKNN3 1.0.5b10

#include "Tokenizer.h"
#include "float16.h"
#include "rknn3_api.h"

#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/un.h>
#include <unistd.h>

#include <string>
#include <vector>

#define LOGW(fmt, ...) fprintf(stderr, "\033[33m" fmt "\033[0m", ##__VA_ARGS__)
#define DEFAULT_SOCK "/tmp/r1-llm.sock"

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
    send_error(fd, g_req_id.c_str(), "inference error");
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

    std::string line = "{\"type\":\"token\",\"id\":\"";
    line += g_req_id;
    line += "\",\"text\":\"";
    json_escape_append(piece.c_str(), line);
    line += "\"}";
    send_line(fd, line);
  }
  return 0;
}

static int init_context_and_model(rknn3_context *p_ctx, const char *model_path, const char *weight_path,
                                  uint32_t core_mask, const char *device_id)
{
  rknn3_config config;
  rknn3_context ctx = 0;
  rknn3_init_extend init_extend = {0};
  init_extend.device_id = (char *)device_id;
  int ret = rknn3_init(&ctx, &init_extend);
  if (ret < 0)
    return ret;

  memset(&config, 0, sizeof(config));
  config.model_path = (char *)model_path;
  config.weight_path = (char *)weight_path;
  config.core_mask = core_mask;
  ret = rknn3_load_model(ctx, &config);
  if (ret < 0)
  {
    rknn3_destroy(ctx);
    return ret;
  }
  *p_ctx = ctx;
  return 0;
}

static int get_tokenizer_and_embedding(const char *tokenizer_path, VocabInfo *vocab_info, Tokenizer **tokenizer,
                                       struct embedding_info *embedding_info, const char *embedding_path,
                                       struct stat *emb_st)
{
  *tokenizer = new Tokenizer(tokenizer_path);
  if (!(*tokenizer)->IsLoaded())
  {
    delete *tokenizer;
    *tokenizer = nullptr;
    return -1;
  }
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

  ret = init_context_and_model(&g_ctx, model_path, weight_path, core_mask, device_id);
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

  int ret = rknn3_session_run(g_session, inputs, 1, &infer_param);
  gettimeofday(&g_end, NULL);
  g_client_fd = -1;

  if (ret != RKNN3_SUCCESS)
  {
    pthread_mutex_unlock(&g_infer_mu);
    send_error(fd, req_id.c_str(), "rknn3_session_run failed");
    return false;
  }

  RKLLMRunState state;
  memset(&state, 0, sizeof(state));
  rknn3_session_query_state(g_session, &state);
  if (state.n_total_tokens >= (state.n_max_tokens - max_new))
    rknn3_session_clear_kvcache(g_session, RKNN3_KVCACHE_CLEAR_ALL);

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
           req_id.c_str(), prefill_ms, generate_ms, state.n_decode_tokens);
  send_line(fd, done);
  pthread_mutex_unlock(&g_infer_mu);
  return true;
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
  if (argc < 8)
  {
    LOGW("Usage: %s <rknn> <weight> <tokenizer.gguf> <embed.bin> <ctx> <default_max_new> <core_mask> [sock_path]\n",
         argv[0]);
    return 1;
  }

  signal(SIGINT, on_signal);
  signal(SIGTERM, on_signal);
  if (argc >= 9)
    strncpy(g_sock_path, argv[8], sizeof(g_sock_path) - 1);

  if (init_daemon(argv[1], argv[2], argv[3], argv[4], atoi(argv[5]),
                  (uint32_t)strtoul(argv[7], NULL, 16)) != 0)
  {
    fprintf(stderr, "[daemon] init failed\n");
    return 1;
  }

  int rc = serve_forever();

  if (g_session)
    rknn3_session_destroy(g_session);
  if (g_ctx)
    rknn3_destroy(g_ctx);
  if (g_embed.embedding_data && g_embed.mmap_size)
    munmap(g_embed.embedding_data, g_embed.mmap_size);
  if (g_embed.fd != -1)
    close(g_embed.fd);
  if (g_tokenizer)
    delete g_tokenizer;

  return rc;
}
