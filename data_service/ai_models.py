"""
AI 模型配置 - 支持多种大模型
"""

AI_MODELS = {
    'deepseek': {
        'name': 'DeepSeek',
        'base_url': 'https://api.deepseek.com/v1',
        'models': ['deepseek-chat', 'deepseek-coder'],
    },
    'qwen': {
        'name': '通义千问',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'models': ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen-long'],
    },
    'doubao': {
        'name': '豆包',
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'models': ['doubao-pro-32k', 'doubao-pro-4k', 'doubao-lite-4k', 'doubao-lite-32k'],
    },
    'glm': {
        'name': '智谱 GLM',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'models': ['glm-4', 'glm-4-plus', 'glm-4-flash', 'glm-3-turbo'],
    },
    'kimi': {
        'name': 'Kimi',
        'base_url': 'https://api.moonshot.cn/v1',
        'models': ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
    },
    'openai': {
        'name': 'OpenAI',
        'base_url': 'https://api.openai.com/v1',
        'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
    },
}

AI_MODEL_CONFIGS = AI_MODELS
