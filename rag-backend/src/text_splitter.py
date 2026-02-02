"""
text_splitter - 文档分块

Author: lsy
Date: 2026/1/7
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

class TextSplitter:
    def __init__(self):
        pass

    @staticmethod
    def _format_page_range(start: int, end: int) -> List[int]:
        """返回页码范围，单页返回 [8]，跨页返回 [2, 4]"""
        return [start, end] if start != end else [start]

    def split_single_report(self,report_path_dir,chunk_size:int=500,chunk_overlap: int = 50):
        json_path = Path(report_path_dir) / "block_list.json"
        file_origin=Path(report_path_dir).name # ../data/stock_data/debug_data/【财报】中芯国际：中芯国际2024年年度报告
        # print(file_origin)
        if not json_path.exists():
            raise FileNotFoundError(f"找不到文件: {json_path}")

        chunks = []
        # print(type_set) # {'table_body', 'header', 'text', 'page_number', 'image', 'table_footnote', 'title', 'table_caption'}
        with open(json_path, "r", encoding="utf-8") as f:
            report_data_pages = json.load(f)['pdfData'] # 一个list，每一页是一个list
            print(len(report_data_pages))
            temp_chunk_text = ''
            current_start_page = 1 # 当前块所在的起始页数

            # 表格缓冲区，用于合并跨页表格，还有table类的表格合并问题
            table_buffer: Optional[Dict] = None
            for page_idx,content in enumerate(report_data_pages): # 循环页数
                for metaData in content: # 循环每一页的块数
                    current_end_page = page_idx + 1 # 当前所在页数
                    block_type = metaData['type']

                    # 1. 噪音直接舍弃
                    if metaData.get('is_discarded', False):
                        continue

                    # 2. 处理独立块
                    if block_type in ['table_body', 'image']:
                        # 如果前面有累积的普通文本，先存掉
                        if len(temp_chunk_text) > 0:
                            chunks.append({
                                'page_range': self._format_page_range(current_start_page, page_idx+1),
                                'file_origin': f'{file_origin}.pdf',
                                'text': temp_chunk_text
                            })
                            temp_chunk_text = ''  # 清空缓存

                        # 提取内容
                        special_content = ""
                        if block_type == 'table_body':
                            # 表格数据通常在 content
                            special_content = str(metaData.get('table_body', ''))
                        elif block_type == 'image':
                            # 图片通常是路径或编码，假设字段为 'path'，如果没有则为空字符串
                            special_content = str(metaData.get('img_path', ''))

                        # 将独立内容存入 chunks
                        chunks.append({
                            'page_range': self._format_page_range(current_start_page, current_end_page),
                            'file_origin': f'{file_origin}.pdf',
                            'text': special_content
                        })
                        current_start_page = current_end_page

                    # 3. 处理普通文本类：header, title, text
                    else:
                        # 提取文字内容
                        text_content = metaData.get('text', '')
                        temp_chunk_text += text_content

                        # 检查是否超过切分大小 (比如 300)
                        if len(temp_chunk_text) > chunk_size:
                            chunks.append({
                                'page_range': self._format_page_range(current_start_page, current_end_page),
                                'file_origin': f'{file_origin}.pdf',
                                'text': temp_chunk_text
                            })
                            current_start_page = current_end_page

                            # 实现重叠逻辑
                            # 清空缓存，但保留最后 chunk_overlap 个字符
                            if 0 < chunk_overlap < len(temp_chunk_text):
                                temp_chunk_text = temp_chunk_text[-chunk_overlap:]
                            else:
                                # 如果文本本身比重叠长度还短，或者不设置重叠，则清空
                                temp_chunk_text = ''

            # 所有页都循环完后，检查最后剩下的文本（尾巴）
            if len(temp_chunk_text) > 0:
                chunks.append({
                    'page_range': [current_end_page],
                    'file_origin': f'{file_origin}.pdf',
                    'text': temp_chunk_text
                })

        return chunks


    def split_all_reports(self,all_report_dir:Path,output_dir:Path):
        print(f'目标目录: {all_report_dir},输出目录: {output_dir}')# 目标目录，输出目录
        reports_list = os.listdir(all_report_dir)
        for report_path in reports_list:
            # print(report_path) #【财报】中芯国际：中芯国际2024年年度报告
            report_path_dir=os.path.join(all_report_dir,report_path)
            if os.path.isdir(report_path_dir):
                chunks = self.split_single_report(report_path_dir,500,50)
                output_data={
                    "metainfo":{
                        "file_name":report_path
                    },
                    "content":{
                        "chunks":chunks
                    }
                }
                with open(os.path.join(output_dir,f'{report_path}.json'),'w',encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=4)
        print('切割完成')




