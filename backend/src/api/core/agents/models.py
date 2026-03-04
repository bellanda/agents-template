from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    provider: str
    reasoning: bool = False  # emits reasoning_content in stream (Chutes/Cerebras)
    thinking: bool = False   # emits thinking blocks in stream (NVIDIA)


class Models:
    """Model registry. Use init_model(Models.Provider.NAME) in each agent to instantiate."""

    class Cerebras:
        GPT_OSS_120B     = ModelConfig("gpt-oss-120b",                     "cerebras")
        ZAI_GLM_4_7      = ModelConfig("zai-glm-4.7",                      "cerebras")
        LLAMA_3_1_8B     = ModelConfig("llama3.1-8b",                      "cerebras")
        QWEN_3_235B_A22B = ModelConfig("qwen-3-235b-a22b-instruct-2507",   "cerebras")

    class Chutes:
        QWEN3_5_397B_A17B_TEE = ModelConfig("Qwen/Qwen3.5-397B-A17B-TEE",          "chutes", reasoning=True)
        MINIMAX_M2_5_TEE      = ModelConfig("MiniMaxAI/MiniMax-M2.5-TEE",          "chutes", reasoning=True)
        GLM_5_TEE             = ModelConfig("zai-org/GLM-5-TEE",                   "chutes", reasoning=True)
        KIMI_K2_5_TEE         = ModelConfig("moonshotai/Kimi-K2.5-TEE",            "chutes", reasoning=True)
        GPT_OSS_120B_TEE      = ModelConfig("openai/gpt-oss-120b-TEE",             "chutes", reasoning=True)
        GPT_OSS_20B           = ModelConfig("openai/gpt-oss-20b",                  "chutes", reasoning=True)
        DEEPSEEK_V3_2_TEE     = ModelConfig("deepseek-ai/DeepSeek-V3.2-TEE",       "chutes", reasoning=True)

    class Google:
        GEMINI_3_1_PRO_PREVIEW = ModelConfig("gemini-3.1-pro-preview", "google")
        GEMINI_3_FLASH_PREVIEW = ModelConfig("gemini-3-flash-preview", "google")

    class Groq:
        GPT_OSS_120B     = ModelConfig("openai/gpt-oss-120b",                           "groq")
        GPT_OSS_20B      = ModelConfig("openai/gpt-oss-20b",                            "groq")
        LLAMA_4_SCOUT    = ModelConfig("meta-llama/llama-4-scout-17b-16e-instruct",     "groq")
        KIMI_K2_INSTRUCT = ModelConfig("moonshotai/kimi-k2-instruct-0905",              "groq")

    class NVIDIA:
        GLM5              = ModelConfig("z-ai/glm5",                        "nvidia", thinking=True)
        QWEN3_5_397B_A17B = ModelConfig("qwen/qwen3.5-397b-a17b",          "nvidia", thinking=True)
        MINIMAX_M2_1      = ModelConfig("minimaxai/minimax-m2.1",           "nvidia", thinking=True)
        STEP_3_5_FLASH    = ModelConfig("stepfun-ai/step-3.5-flash",        "nvidia")
        KIMI_K2_5         = ModelConfig("moonshotai/kimi-k2.5",             "nvidia", thinking=True)
        DEEPSEEK_V3_2     = ModelConfig("deepseek-ai/deepseek-v3.2",        "nvidia", thinking=True)
        NEMOTRON_3_NANO   = ModelConfig("nvidia/nemotron-3-nano-30b-a3b",   "nvidia", thinking=True)
        GPT_OSS_120B      = ModelConfig("openai/gpt-oss-120b",              "nvidia", thinking=True)
        GPT_OSS_20B       = ModelConfig("openai/gpt-oss-20b",               "nvidia", thinking=True)
