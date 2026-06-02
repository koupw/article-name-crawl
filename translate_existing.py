"""对现有 Markdown 文件中的论文标题进行翻译"""

import re
import sys
from pathlib import Path

from utils.translator import translate_to_chinese


def parse_markdown_table(content: str) -> list[dict]:
    """解析 Markdown 表格中的论文

    Args:
        content: Markdown 文件内容

    Returns:
        论文信息列表
    """
    papers = []
    lines = content.split('\n')

    # 查找表格
    in_table = False
    headers = []

    for line in lines:
        line = line.strip()

        # 检测表格开始
        if '|' in line and '---' not in line:
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]

            if not in_table:
                # 第一行是表头
                headers = cells
                in_table = True
                continue

            # 数据行
            if len(cells) >= len(headers):
                paper = {}
                for i, header in enumerate(headers):
                    if i < len(cells):
                        paper[header] = cells[i]
                papers.append(paper)

        elif in_table and line == '':
            # 表格结束
            in_table = False
            headers = []

    return papers


def extract_title_from_cell(title_cell: str) -> str:
    """从 Markdown 链接中提取标题

    Args:
        title_cell: 标题单元格内容，可能是 [标题](url) 格式

    Returns:
        纯标题文本
    """
    # 匹配 [标题](url) 格式
    match = re.match(r'\[(.+?)\]\(.+?\)', title_cell)
    if match:
        return match.group(1)

    # 检查是否有省略号
    if title_cell.endswith('...'):
        return title_cell[:-3]

    return title_cell


def translate_markdown_file(input_path: Path, output_path: Path = None):
    """翻译 Markdown 文件中的论文标题

    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径（默认为覆盖原文件）
    """
    if output_path is None:
        output_path = input_path

    print(f"读取文件: {input_path}")

    # 读取文件
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析表格
    papers = parse_markdown_table(content)
    print(f"找到 {len(papers)} 篇论文")

    if not papers:
        print("未找到论文表格")
        return

    # 翻译标题
    print("开始翻译...")
    translated_content = content

    for i, paper in enumerate(papers):
        # 获取标题
        title_cell = paper.get('标题', '')
        if not title_cell:
            continue

        # 提取纯标题
        title = extract_title_from_cell(title_cell)

        # 翻译
        print(f"  [{i+1}/{len(papers)}] {title[:50]}...")
        title_zh = translate_to_chinese(title)

        if title_zh:
            print(f"    -> {title_zh}")

            # 检查是否已有中文标题列
            if '中文标题' not in paper:
                # 需要添加中文标题列
                # 找到表格行并添加中文标题
                # 这种方式比较复杂，我们用更简单的方法
                pass

    # 重新构建文件（更可靠的方式）
    lines = content.split('\n')
    new_lines = []
    in_table = False
    headers = []
    table_started = False

    for line in lines:
        stripped = line.strip()

        if '|' in stripped and '---' not in stripped:
            cells = [cell.strip() for cell in stripped.split('|') if cell.strip()]

            if not in_table:
                # 表头行
                headers = cells
                in_table = True

                # 检查是否需要添加中文标题列
                if '中文标题' not in headers:
                    # 在标题后添加中文标题列
                    title_idx = headers.index('标题') if '标题' in headers else 1
                    headers.insert(title_idx + 1, '中文标题')
                    new_line = '| ' + ' | '.join(headers) + ' |'
                    new_lines.append(new_line)

                    # 添加分隔行
                    sep_cells = ['---'] * len(headers)
                    new_line = '| ' + ' | '.join(sep_cells) + ' |'
                    new_lines.append(new_line)
                else:
                    new_lines.append(line)

                continue

            # 数据行
            if len(cells) >= len(headers) - 1:  # 允许少一列（可能是旧格式）
                # 提取标题
                title_cell = cells[1] if len(cells) > 1 else ''  # 假设标题在第二列
                title = extract_title_from_cell(title_cell)

                # 翻译
                title_zh = translate_to_chinese(title)

                # 构建新行
                if '中文标题' not in [h.strip() for h in stripped.split('|') if h.strip()]:
                    # 需要添加中文标题列
                    title_idx = 1  # 标题列索引
                    new_cells = cells[:title_idx + 1] + [title_zh or '-'] + cells[title_idx + 1:]
                else:
                    # 已有中文标题列，更新它
                    new_cells = cells.copy()
                    zh_idx = [h.strip() for h in stripped.split('|') if h.strip()].index('中文标题')
                    if zh_idx < len(new_cells):
                        new_cells[zh_idx] = title_zh or '-'

                new_line = '| ' + ' | '.join(new_cells) + ' |'
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        elif in_table and stripped == '':
            # 表格结束
            in_table = False
            headers = []
            new_lines.append(line)

        else:
            new_lines.append(line)

    # 写入文件
    new_content = '\n'.join(new_lines)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"\n翻译完成！文件已保存到: {output_path}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        # 默认处理 papers 目录下的所有 Markdown 文件
        papers_dir = Path('./papers')
        if not papers_dir.exists():
            print("未找到 papers 目录")
            return

        md_files = list(papers_dir.glob('*.md'))
        if not md_files:
            print("未找到 Markdown 文件")
            return

        for md_file in md_files:
            print(f"\n处理文件: {md_file}")
            translate_markdown_file(md_file)
    else:
        # 处理指定文件
        input_path = Path(sys.argv[1])
        if not input_path.exists():
            print(f"文件不存在: {input_path}")
            return

        translate_markdown_file(input_path)


if __name__ == '__main__':
    main()
