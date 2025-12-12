"""Markdown processing utilities - pure functions without workflow dependencies."""


def merge_markdown_contents(files_data: list[tuple[str, str]]) -> str:
    """
    合并多个 MD 文件内容
    
    Args:
        files_data: [(filename, content), ...] 列表
        
    Returns:
        合并后的 Markdown 内容
        
    Notes:
        - 单文件：直接返回内容
        - 多文件：按原顺序拼接 `<!-- Source: filename -->` 注释 + content.strip() + 空行分隔
    """
    if len(files_data) == 1:
        # 单个文件直接返回内容
        return files_data[0][1]
    
    # 多个文件用 HTML 注释标记来源
    merged_parts = []
    for filename, content in files_data:
        merged_parts.append(f"<!-- Source: {filename} -->")
        merged_parts.append(content.strip())
        merged_parts.append("")  # 空行分隔
    
    return "\n".join(merged_parts)