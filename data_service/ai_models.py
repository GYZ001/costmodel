"""
AI 模型配置 - 支持多种大模型
"""

AI_MODELS = {
    'deepseek': {
        'name': 'DeepSeek',
        'base_url': 'https://api.deepseek.com',
        'models': ['deepseek-v4-flash', 'deepseek-v4-pro', 'deepseek-chat', 'deepseek-reasoner'],
    },
    'qwen': {
        'name': '通义千问',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'models': ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-long', 'qwen3-235b-a22b'],
    },
    'doubao': {
        'name': '豆包',
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'models': ['doubao-1-5-pro-32k', 'doubao-1-5-lite-32k', 'doubao-pro-32k', 'doubao-lite-32k'],
    },
    'glm': {
        'name': '智谱 GLM',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'models': ['glm-4-plus', 'glm-4-air', 'glm-4-flash', 'glm-z1-flash'],
    },
    'kimi': {
        'name': 'Kimi',
        'base_url': 'https://api.moonshot.cn/v1',
        'models': ['kimi-latest', 'moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k'],
    },
    'openai': {
        'name': 'OpenAI',
        'base_url': 'https://api.openai.com/v1',
        'models': ['gpt-4.1', 'gpt-4.1-mini', 'gpt-4o', 'gpt-4o-mini', 'o3', 'o3-mini'],
    },
}

AI_MODEL_CONFIGS = AI_MODELS
