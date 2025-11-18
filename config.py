import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

class Config:
    """配置管理类"""
    
    # 项目路径
    PROJECT_ROOT = Path(__file__).parent
    DIST_DIR = PROJECT_ROOT / "dist"
    TESTS_DIR = PROJECT_ROOT / "tests"
    TEMPLATES_DIR = TESTS_DIR / "templates"
    GENERATED_DIR = TESTS_DIR / "generated"
    UTILS_DIR = PROJECT_ROOT / "utils"
    
    # AI 模型配置
    AI_MODEL = "qwen-plus-latest"
    AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    AI_TEMPERATURE_STABLE = 0.1  # 最稳定输出（用于代码生成）
    AI_TEMPERATURE_CREATIVE = 0.3  # 稍有创造性（用于分析）
    
    # MCP 配置
    MCP_MAX_ITERATIONS = 15  # 最大工具调用轮数
    MCP_TIMEOUT = 30  # MCP 调用超时（秒）
    
    # 测试生成配置
    TEST_FILE_ENCODING = "utf-8"
    DEFAULT_BROWSER = "chromium"  # chromium, firefox, webkit
    
    # 本地服务器配置
    LOCAL_SERVER_PORT_RANGE = (8000, 9000)
    LOCAL_SERVER_HOST = "127.0.0.1"
    
    def __init__(self):
        """初始化配置"""
        self._api_key = None
        self._custom_config = None
        self._load_config_file()
    
    def _load_config_file(self):
        """加载配置文件（如果存在）"""
        config_file = self.PROJECT_ROOT / "config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self._custom_config = json.load(f)
            except Exception as e:
                print(f"警告: 加载配置文件失败: {e}")
    
    @property
    def api_key(self) -> str:
        """获取 API Key"""
        if self._api_key:
            return self._api_key
        
        # 优先从环境变量读取
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if api_key:
            return api_key
        
        # 其次从配置文件读取
        if self._custom_config and "api_key" in self._custom_config:
            return self._custom_config["api_key"]
        
        raise ValueError(
            "未找到 API Key。请设置环境变量 DASHSCOPE_API_KEY "
            "或在 config.json 中配置 api_key"
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取自定义配置项
        
        Args:
            key: 配置项名称
            default: 默认值
            
        Returns:
            配置值
        """
        if self._custom_config and key in self._custom_config:
            return self._custom_config[key]
        return default
    
    def ensure_dirs(self):
        """确保必要的目录存在"""
        self.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        self.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        self.UTILS_DIR.mkdir(parents=True, exist_ok=True)


# 全局配置实例
config = Config()
config.ensure_dirs()

