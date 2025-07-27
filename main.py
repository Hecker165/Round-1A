import json
import re
import sys
import time
import fitz
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Any

def get_base_style(lines: List[Dict]) -> Dict:
    styles = [
        (round(l['size']), l['font']) for l in lines
        if len(l.get('text', '').split()) > 15 and l.get('text', '').endswith('.')
    ]
    if not styles:
        styles = [(round(l['size']), l['font']) for l in lines if len(l.get('text', '').split()) > 10]
    if not styles: return {'size': 10, 'font': 'default', 'is_bold': False}
    size, font = Counter(styles).most_common(1)[0][0]
    return {'size': size, 'font': font, 'is_bold': 'bold' in font.lower()}

def group_lines(doc: fitz.Document) -> List[Dict]:
    all_lines = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_SEARCH)["blocks"]
        for b in blocks:
            if b['type'] == 0:
                for l in b['lines']:
                    text = " ".join(s['text'].strip() for s in l['spans'] if s['text'].strip())
                    if not text: continue
                    spans = l['spans']
                    font_sizes = [round(s['size']) for s in spans]
                    fonts = [s['font'] for s in spans]
                    size = Counter(font_sizes).most_common(1)[0][0] if font_sizes else 0
                    font = Counter(fonts).most_common(1)[0][0] if fonts else ""
                    all_lines.append({
                        'text': text, 'size': size, 'font': font,
                        'bbox': l['bbox'], 'page_num': page_num,
                        'is_bold': 'bold' in font.lower()
                    })
    return sorted(all_lines, key=lambda x: (x['page_num'], x['bbox'][1]))

def get_level_from_numbering(text: str) -> str:
    match = re.match(r'^\s*([IVXLCDM]+\.|\d+(\.\d+)*)[\.\s]+', text, re.IGNORECASE)
    if not match:
        if re.match(r'^(Appendix\s+[A-Z])', text, re.IGNORECASE): return 'H1'
        return None
    depth = match.group(1).count('.')
    return f'H{min(depth + 1, 4)}'

def is_valid_candidate(line: Dict, prev_line: Dict, base_style: Dict) -> bool:
    text = line['text']
    has_space_above = line['page_num'] != prev_line['page_num'] or \
                      (line['bbox'][1] - prev_line['bbox'][3] > 4)
    is_stylistically_different = line['size'] > base_style['size'] or \
                               (line['is_bold'] and not base_style['is_bold'])
    is_short = len(text.split()) < 25
    is_not_body_text = not text.endswith(('.', ',', ';')) or len(text.split()) < 5
    non_alpha_ratio = len(re.findall(r'[^a-zA-Z\d\s]', text)) / len(text) if len(text) > 0 else 0
    if non_alpha_ratio > 0.3 and '---' in text: return False
    if re.fullmatch(r'[\s\d\.\-]+', text): return False
    if text.lower().startswith(('figure', 'table', 'copyright', 'page')): return False
    return has_space_above and is_stylistically_different and is_short and is_not_body_text

def assign_heading_levels(headings: List[Dict]) -> List[Dict]:
    if not headings:
        return []
    style_to_level = {}
    for h in headings:
        level = get_level_from_numbering(h['text'])
        if level:
            style_key = (h['size'], h['font'])
            if style_key not in style_to_level or int(level[1:]) < int(style_to_level[style_key][1:]):
                style_to_level[style_key] = level
    unleveled_styles = {(h['size'], h['font']) for h in headings if get_level_from_numbering(h['text']) is None}
    def get_style_rank(style):
        size, font = style
        return size * 2 + (10 if 'bold' in font.lower() else 0)
    sorted_styles = sorted(list(unleveled_styles), key=get_style_rank, reverse=True)
    next_level = 1
    for style in sorted_styles:
        if style not in style_to_level:
            if next_level > 3: break
            style_to_level[style] = f"H{next_level}"
            next_level += 1
    for h in headings:
        level = get_level_from_numbering(h['text'])
        if not level:
            level = style_to_level.get((h['size'], h['font']))
        h['level'] = level
    return [h for h in headings if h.get('level')]

def find_title(lines: List[Dict], page_width: float) -> str:
    candidates = []
    for line in lines:
        if line['page_num'] != 0 or len(line['text'].split()) > 20 or len(line['text'].split()) < 2: continue
        score = line['size'] * 1.5 - (line['bbox'][1] * 0.1)
        if line['is_bold']: score += 5
        if abs((line['bbox'][0] + line['bbox'][2]) / 2 - page_width / 2) < page_width * 0.2: score += 10
        if line['text'].isupper(): score += 5
        if score > 0: candidates.append({'score': score, 'text': line['text']})
    if not candidates: return ""
    best_candidate = sorted(candidates, key=lambda x: -x['score'])[0]
    return best_candidate['text'] if best_candidate['score'] > 35 else ""

def process_pdf(pdf_path: Path) -> Dict[str, Any]:
    try:
        doc = fitz.open(str(pdf_path))
        lines = group_lines(doc)
        if not lines: return {"title": "", "outline": []}
        title = find_title(lines, doc[0].rect.width)
        base_style = get_base_style(lines)
        candidates = []
        for i, line in enumerate(lines):
            if i > 0 and line['text'] != title:
                if is_valid_candidate(line, lines[i-1], base_style):
                    candidates.append(line)
        headings = assign_heading_levels(candidates)
        seen_text = set()
        final_outline = []
        for h in sorted(headings, key=lambda x: (x['page_num'], x['bbox'][1])):
            if h['text'] not in seen_text:
                final_outline.append({'level': h['level'], 'text': h['text'], 'page': h['page_num'] + 1})
                seen_text.add(h['text'])
        if not title and final_outline and final_outline[0]['level'] == 'H1':
            first_heading_line = next((l for l in lines if l['text'] == final_outline[0]['text']), None)
            if first_heading_line and first_heading_line['bbox'][1] < 200:
                title = final_outline.pop(0)['text']
        doc.close()
        return {"title": title, "outline": final_outline}
    except Exception as e:
        return {"title": str(pdf_path.stem), "outline": []}

def main():
    if len(sys.argv) < 3 or '--outdir' not in sys.argv:
        sys.exit("Usage: python3 extract_outline.py <input_dir> --outdir <output_dir>")
    input_dir, output_dir = Path(sys.argv[1]), Path(sys.argv[sys.argv.index('--outdir') + 1])
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {input_dir}")
        return
    print(f"Found {len(pdf_files)} PDF file(s) to process.")
    start_time = time.time()
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}")
        result = process_pdf(pdf_file)
        with open(output_dir / f"{pdf_file.stem}.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        print(f"  -> Created: {output_dir / f'{pdf_file.stem}.json'}")
    print(f"\nCompleted in {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()