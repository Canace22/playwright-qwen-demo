"""
公共函数库
提供跨模块复用的工具函数
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from openai import OpenAI


# 配置日志
def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    配置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        
    Returns:
        配置好的 logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加 handler
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


# 初始化 OpenAI 客户端
def create_openai_client(api_key: Optional[str] = None) -> OpenAI:
    """
    创建 OpenAI 客户端（用于通义千问）
    
    Args:
        api_key: API Key，如果为 None 则从环境变量读取
        
    Returns:
        OpenAI 客户端实例
    """
    if api_key is None:
        api_key = os.getenv("DASHSCOPE_API_KEY")
    
    if not api_key:
        raise ValueError("未设置 DASHSCOPE_API_KEY 环境变量")
    
    return OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


# 代码处理函数
def extract_code_from_markdown(content: str) -> str:
    """
    从 markdown 格式中提取纯代码
    
    Args:
        content: 可能包含 markdown 的内容
        
    Returns:
        提取的代码
    """
    if not content:
        return "// 未生成代码"
    
    # 尝试提取 markdown 代码块
    code_block_pattern = r"```(?:javascript|js|typescript|ts)?\s*\n(.*?)\n```"
    matches = re.findall(code_block_pattern, content, re.DOTALL)
    
    if matches:
        # 返回第一个代码块
        return matches[0].strip()
    else:
        # 没有代码块，返回原始内容
        return content.strip()


def convert_require_to_import(code: str) -> str:
    """
    将 CommonJS require 语法转换为 ES6 import 语法
    
    Args:
        code: 原始代码
        
    Returns:
        转换后的代码
    """
    def replace_destructure(match):
        """替换解构导入"""
        content = match.group(1).strip()
        module = match.group(2)
        semicolon = match.group(3) if match.lastindex >= 3 else ''
        return f"import {{ {content} }} from '{module}'{semicolon}"
    
    def replace_default(match):
        """替换默认导入"""
        name = match.group(1)
        module = match.group(2)
        semicolon = match.group(3) if match.lastindex >= 3 else ''
        return f"import {name} from '{module}'{semicolon}"
    
    # 匹配 const { a, b } = require('module');
    pattern1 = r"const\s+\{\s*([^}]+)\s*\}\s*=\s*require\(['\"]([^'\"]+)['\"]\)(;?)"
    code = re.sub(pattern1, replace_destructure, code)
    
    # 匹配 const name = require('module');
    pattern2 = r"const\s+(\w+)\s*=\s*require\(['\"]([^'\"]+)['\"]\)(;?)"
    code = re.sub(pattern2, replace_default, code)
    
    return code


def clean_generated_code(code: str) -> str:
    """
    清理生成的代码（提取 + 转换）
    
    Args:
        code: AI 生成的原始代码
        
    Returns:
        清理后的代码
    """
    # 1. 提取代码块
    code = extract_code_from_markdown(code)
    
    # 2. 转换 require 为 import
    code = convert_require_to_import(code)
    
    return code


# 文件操作函数
def save_test_file(code: str, output_path: Path, encoding: str = 'utf-8') -> bool:
    """
    保存测试文件
    
    Args:
        code: 测试代码
        output_path: 输出路径
        encoding: 文件编码
        
    Returns:
        是否保存成功
    """
    try:
        # 确保目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存文件
        with open(output_path, 'w', encoding=encoding) as f:
            f.write(code)
        
        return True
    except Exception as e:
        logging.error(f"保存文件失败: {e}")
        return False


def read_file_safe(file_path: Path, encoding: str = 'utf-8') -> Optional[str]:
    """
    安全读取文件
    
    Args:
        file_path: 文件路径
        encoding: 文件编码
        
    Returns:
        文件内容，失败返回 None
    """
    try:
        if not file_path.exists():
            return None
        
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        logging.error(f"读取文件失败 {file_path}: {e}")
        return None


# AI 调用函数
def call_ai_with_retry(
    client: OpenAI,
    messages: list,
    model: str = "qwen-plus-latest",
    temperature: float = 0.1,
    max_retries: int = 3,
    **kwargs
) -> Optional[str]:
    """
    调用 AI 并自动重试
    
    Args:
        client: OpenAI 客户端
        messages: 消息列表
        model: 模型名称
        temperature: 温度
        max_retries: 最大重试次数
        **kwargs: 其他参数
        
    Returns:
        AI 响应内容，失败返回 None
    """
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.warning(f"AI 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                logging.error("AI 调用最终失败")
                return None
    
    return None


# JSON 处理函数
def safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    """
    安全解析 JSON（自动清理 markdown 格式）
    
    Args:
        text: 可能包含 JSON 的文本
        
    Returns:
        解析后的字典，失败返回 None
    """
    try:
        # 移除可能的 markdown 代码块标记
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        logging.error(f"JSON 解析失败: {e}")
        return None


# 路径处理函数
def resolve_path(path: str, base_dir: Optional[Path] = None) -> Path:
    """
    解析路径（支持相对路径和绝对路径）
    
    Args:
        path: 路径字符串
        base_dir: 基础目录（用于相对路径）
        
    Returns:
        绝对路径
    """
    path_obj = Path(path)
    
    if path_obj.is_absolute():
        return path_obj
    else:
        if base_dir is None:
            base_dir = Path.cwd()
        return (base_dir / path_obj).resolve()


# 格式化输出函数
def format_validation_result(result: Dict[str, Any]) -> str:
    """
    格式化验证结果为易读文本
    
    Args:
        result: 验证结果字典
        
    Returns:
        格式化后的文本
    """
    lines = []
    lines.append("=" * 60)
    lines.append(f"验证结果: {'✅ 通过' if result['valid'] else '❌ 失败'}")
    lines.append(f"质量评分: {result['score']}/100")
    lines.append("=" * 60)
    
    if result['errors']:
        lines.append("\n❌ 错误:")
        for error in result['errors']:
            lines.append(f"  - {error}")
    
    if result['warnings']:
        lines.append("\n⚠️  警告:")
        for warning in result['warnings']:
            lines.append(f"  - {warning}")
    
    if result['suggestions']:
        lines.append("\n💡 建议:")
        for suggestion in result['suggestions']:
            lines.append(f"  - {suggestion}")
    
    lines.append("=" * 60)
    return "\n".join(lines)


# 使用示例
if __name__ == "__main__":
    # 测试代码清理
    sample = """
```javascript
const { test, expect } = require('@playwright/test');
test('example', () => {});
```
    """
    
    cleaned = clean_generated_code(sample)
    print("清理后的代码:")
    print(cleaned)

