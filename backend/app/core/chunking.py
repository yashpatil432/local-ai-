import re
from typing import List, Dict, Any, Optional
from backend.app.models.schemas import Chunk, DocumentMetadata

def parse_markdown_pages(content: str) -> List[Dict[str, Any]]:
    """
    Splits document by `<!-- PAGE: X -->` markers.
    If no page markers exist, returns page 1.
    """
    page_splits = re.split(r'<!--\s*PAGE:\s*(\d+)\s*-->', content)
    pages = []
    
    if len(page_splits) == 1:
        pages.append({"page_num": 1, "text": content.strip()})
        return pages
    
    # page_splits has format: [preamble, page_1_num, page_1_text, page_2_num, page_2_text, ...]
    preamble = page_splits[0].strip()
    if preamble:
        pages.append({"page_num": 1, "text": preamble})
        
    for i in range(1, len(page_splits), 2):
        if i + 1 < len(page_splits):
            page_num = int(page_splits[i])
            page_text = page_splits[i + 1].strip()
            pages.append({"page_num": page_num, "text": page_text})
            
    return pages

def extract_tables_from_markdown(text: str) -> List[Dict[str, str]]:
    """
    Extracts markdown tables and converts them into structured context strings.
    E.g. Table: | Col1 | Col2 | converted to structured rows.
    """
    table_pattern = re.compile(r'(\|.+?\|\n\|[-:\s|]+\|\n(?:\|.+?\|\n?)+)', re.MULTILINE)
    tables = []
    for match in table_pattern.finditer(text):
        raw_table = match.group(0).strip()
        lines = [line.strip() for line in raw_table.split('\n') if line.strip()]
        if len(lines) >= 3:
            headers = [c.strip() for c in lines[0].split('|')[1:-1]]
            rows = []
            for row_line in lines[2:]:
                cells = [c.strip() for c in row_line.split('|')[1:-1]]
                row_str = ", ".join([f"{headers[idx] if idx < len(headers) else f'Col{idx}'}: {cells[idx]}" for idx in range(min(len(headers), len(cells)))])
                rows.append(row_str)
            structured_repr = " [Structured Table: " + "; ".join(rows) + "] "
            tables.append({"raw": raw_table, "structured": structured_repr})
    return tables

def chunk_document(doc_meta: DocumentMetadata, raw_content: str) -> List[Chunk]:
    """
    Structure-aware chunker that:
    1. Splits into pages
    2. Identifies sections and headings within each page
    3. Preserves table context
    4. Attaches rich metadata to each chunk
    """
    pages = parse_markdown_pages(raw_content)
    chunks: List[Chunk] = []
    chunk_counter = 1
    
    current_doc_title = doc_meta.title
    current_department = doc_meta.department
    
    for page in pages:
        page_num = page["page_num"]
        page_text = page["text"]
        
        # Check for tables on this page
        extracted_tables = extract_tables_from_markdown(page_text)
        table_context_str = " ".join([t["structured"] for t in extracted_tables]) if extracted_tables else None
        
        # Split by section headers (## Section X or ### Subheading)
        sections = re.split(r'(?m)(?=^#{2,3}\s+)', page_text)
        
        for section_block in sections:
            section_block = section_block.strip()
            if not section_block:
                continue
                
            # Extract section heading
            heading_match = re.match(r'^#{2,3}\s+(.+)', section_block)
            if heading_match:
                section_name = heading_match.group(1).strip()
            else:
                section_name = f"General Provision - Page {page_num}"
                
            # If section is excessively long (more than 1200 chars), split by paragraph
            if len(section_block) > 1200:
                paragraphs = [p.strip() for p in section_block.split('\n\n') if p.strip()]
                buffer = ""
                for p in paragraphs:
                    if len(buffer) + len(p) < 900:
                        buffer += ("\n\n" if buffer else "") + p
                    else:
                        if buffer:
                            chunk_id = f"{doc_meta.id}_p{page_num}_c{chunk_counter}"
                            chunks.append(Chunk(
                                id=chunk_id,
                                document_id=doc_meta.id,
                                document_title=current_doc_title,
                                department=current_department,
                                page=page_num,
                                section=section_name,
                                language=doc_meta.language,
                                published=doc_meta.publication_date,
                                last_updated=doc_meta.last_updated_date,
                                status=doc_meta.status,
                                text=buffer,
                                table_context=table_context_str,
                                metadata={
                                    "url": doc_meta.url,
                                    "version": doc_meta.version,
                                    "category": doc_meta.category,
                                    "gr_number": doc_meta.gr_number,
                                    "title_mr": doc_meta.title_mr
                                }
                            ))
                            chunk_counter += 1
                        buffer = p
                if buffer:
                    chunk_id = f"{doc_meta.id}_p{page_num}_c{chunk_counter}"
                    chunks.append(Chunk(
                        id=chunk_id,
                        document_id=doc_meta.id,
                        document_title=current_doc_title,
                        department=current_department,
                        page=page_num,
                        section=section_name,
                        language=doc_meta.language,
                        published=doc_meta.publication_date,
                        last_updated=doc_meta.last_updated_date,
                        status=doc_meta.status,
                        text=buffer,
                        table_context=table_context_str,
                        metadata={
                            "url": doc_meta.url,
                            "version": doc_meta.version,
                            "category": doc_meta.category,
                            "gr_number": doc_meta.gr_number,
                            "title_mr": doc_meta.title_mr
                        }
                    ))
                    chunk_counter += 1
            else:
                chunk_id = f"{doc_meta.id}_p{page_num}_c{chunk_counter}"
                bilingual_header = f"[{doc_meta.title} / {doc_meta.title_mr or ''}]\n" if doc_meta.title_mr else ""
                chunks.append(Chunk(
                    id=chunk_id,
                    document_id=doc_meta.id,
                    document_title=current_doc_title,
                    department=current_department,
                    page=page_num,
                    section=section_name,
                    language=doc_meta.language,
                    published=doc_meta.publication_date,
                    last_updated=doc_meta.last_updated_date,
                    status=doc_meta.status,
                    text=bilingual_header + section_block,
                    table_context=table_context_str,
                    metadata={
                        "url": doc_meta.url,
                        "version": doc_meta.version,
                        "category": doc_meta.category,
                        "gr_number": doc_meta.gr_number,
                        "title_mr": doc_meta.title_mr,
                        "department_mr": doc_meta.department_mr
                    }
                ))
                chunk_counter += 1

    return chunks
