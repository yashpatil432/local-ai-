import io
import json
import urllib.request
from PIL import Image, ImageDraw
from pypdf import PdfWriter

session_id = 'test-session-e2e'

# 1. Create Document A (Digital PDF with text stream)
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=letter)
    c.drawString(50, 750, 'MAHARASHTRA SOLAR ROOFTOP POLICY 2026')
    c.drawString(50, 720, '1. Eligibility Criteria and Rules:')
    c.drawString(50, 700, 'Residential households with valid electricity meter shall receive 40% capital subsidy.')
    c.drawString(50, 680, 'The maximum annual household income limit is Rs. 12,00,000 for special subsidies.')
    c.drawString(50, 650, '2. Important Statutory Dates:')
    c.drawString(50, 630, 'Application window opens on 1st March 2026 and closes on 30th November 2026.')
    c.drawString(50, 600, '3. Mandatory Key Points:')
    c.drawString(50, 580, 'Grid synchronization inspection must be completed within 15 days of installation.')
    c.save()
    pdf_a_bytes = pdf_buf.getvalue()
    print('Reportlab used for Digital PDF')
except ImportError:
    pdf_text = """%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 390 >> stream
BT
/F1 14 Tf
50 750 Td (MAHARASHTRA SOLAR ROOFTOP SUBSIDY POLICY 2026) Tj
0 -30 Td /F1 11 Tf (1. Eligibility: Residential consumers receive 40% capital subsidy with income limit Rs. 1200000.) Tj
0 -30 Td (2. Dates: Application window opens on 1st March 2026 and closes on 30th November 2026.) Tj
0 -30 Td (3. Rules: Mandatory grid synchronization inspection within 15 working days.) Tj
ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000685 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
755
%%EOF"""
    pdf_a_bytes = pdf_text.encode('latin1')
    print('Raw valid PDF stream generated for Digital PDF')

# 2. Create Document B (Scanned Image PDF)
img_b = Image.new('RGB', (600, 250), color=(255, 255, 255))
d_b = ImageDraw.Draw(img_b)
d_b.text((20, 20), 'DISTRICT HEALTH CARE MISSION MANDATE', fill=(0, 0, 0))
d_b.text((20, 60), 'Free outpatient medicines available to all BPL cardholders.', fill=(0, 0, 0))
d_b.text((20, 100), 'Registration deadline is 15th August 2026 across rural dispensaries.', fill=(0, 0, 0))
d_b.text((20, 140), 'Requirement: Ration card copy and domicile certificate are mandatory.', fill=(0, 0, 0))
pdf_b_io = io.BytesIO()
img_b.save(pdf_b_io, format='PDF')
pdf_b_bytes = pdf_b_io.getvalue()
print('Scanned Image PDF generated')

# Upload both files using multipart/form-data via urllib
import uuid

boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
body = bytearray()

def add_file(field_name, filename, file_data):
    body.extend(f'--{boundary}\r\n'.encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode('utf-8'))
    body.extend(b'Content-Type: application/pdf\r\n\r\n')
    body.extend(file_data)
    body.extend(b'\r\n')

def add_field(field_name, field_val):
    body.extend(f'--{boundary}\r\n'.encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode('utf-8'))
    body.extend(field_val.encode('utf-8'))
    body.extend(b'\r\n')

add_field('session_id', session_id)
add_file('files', 'Solar_Policy_Digital.pdf', pdf_a_bytes)
add_file('files', 'Health_Mission_Scanned.pdf', pdf_b_bytes)
body.extend(f'--{boundary}--\r\n'.encode('utf-8'))

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/user-docs/upload',
    data=bytes(body),
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)

with urllib.request.urlopen(req) as resp:
    upload_res = json.loads(resp.read().decode('utf-8'))
    print('\n=== UPLOAD RESPONSE ===')
    print(f"Total processed: {upload_res['total_processed']}")
    for r in upload_res['results']:
        print(f"File: {r['filename']}, Scanned: {r.get('is_scanned')}, OCR Pages: {r.get('ocr_pages')}, Status: {r['status']}")

# Verify list
req_list = urllib.request.Request(f'http://127.0.0.1:8000/api/user-docs?session_id={session_id}')
with urllib.request.urlopen(req_list) as resp:
    docs = json.loads(resp.read().decode('utf-8'))
    print(f'\n=== LIST USER DOCS (Total: {len(docs)}) ===')
    for d in docs:
        print(f"-> {d['filename']}: pages={d['page_count']}, scanned={d['is_scanned']}, OCR pages={d['ocr_pages']}")

# Test Document Summary
doc_a = next(d for d in docs if 'Solar' in d['filename'])
req_sum = urllib.request.Request(f"http://127.0.0.1:8000/api/user-docs/{doc_a['doc_id']}/summary?session_id={session_id}")
with urllib.request.urlopen(req_sum) as resp:
    sum_data = json.loads(resp.read().decode('utf-8'))
    print('\n=== DOCUMENT SUMMARY (Solar Policy) ===')
    print(f"Short Summary: {sum_data['short_summary']}")
    print(f"Important Dates: {sum_data['important_dates']}")
    print(f"Important Rules: {sum_data['important_rules']}")

# Test Query 1: Digital PDF question
q_payload = json.dumps({'session_id': session_id, 'question': 'What is the income limit for the solar subsidy?', 'doc_id': 'all'}).encode('utf-8')
req_q1 = urllib.request.Request('http://127.0.0.1:8000/api/user-docs/query', data=q_payload, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req_q1) as resp:
    q1_res = json.loads(resp.read().decode('utf-8'))
    print('\n=== QUERY 1 (Digital Doc) ===')
    print('Sufficient:', q1_res['is_sufficient'])
    print('Answer:\n', q1_res['answer'])
    print('Citations:', len(q1_res['citations']))
    assert q1_res['is_sufficient'] == True

# Test Query 2: Scanned OCR PDF question
q_payload2 = json.dumps({'session_id': session_id, 'question': 'What are the mandatory documents for rural dispensaries?', 'doc_id': 'all'}).encode('utf-8')
req_q2 = urllib.request.Request('http://127.0.0.1:8000/api/user-docs/query', data=q_payload2, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req_q2) as resp:
    q2_res = json.loads(resp.read().decode('utf-8'))
    print('\n=== QUERY 2 (Scanned OCR Doc) ===')
    print('Sufficient:', q2_res['is_sufficient'])
    print('Answer:\n', q2_res['answer'])
    print('Citations:', len(q2_res['citations']))
    assert q2_res['is_sufficient'] == True

# Test Query 3: Specific document target query
doc_b = next(d for d in docs if 'Health' in d['filename'])
q_payload_target = json.dumps({'session_id': session_id, 'question': 'What is the registration deadline?', 'doc_id': doc_b['doc_id']}).encode('utf-8')
req_target = urllib.request.Request('http://127.0.0.1:8000/api/user-docs/query', data=q_payload_target, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req_target) as resp:
    target_res = json.loads(resp.read().decode('utf-8'))
    print('\n=== QUERY TARGET (Specific Doc B) ===')
    print('Target Doc Name:', target_res['target_doc_name'])
    print('Answer:\n', target_res['answer'])

# Test Query 4: Strict Zero-Hallucination Refusal
q_payload3 = json.dumps({'session_id': session_id, 'question': 'Does this scheme sponsor interstellar spacecraft missions?', 'doc_id': 'all'}).encode('utf-8')
req_q3 = urllib.request.Request('http://127.0.0.1:8000/api/user-docs/query', data=q_payload3, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req_q3) as resp:
    q3_res = json.loads(resp.read().decode('utf-8'))
    print('\n=== QUERY 4 (Strict Refusal Test) ===')
    print('Sufficient:', q3_res['is_sufficient'])
    print('Answer:', q3_res['answer'])
    assert q3_res['is_sufficient'] == False
    assert "I couldn't find sufficient information about this in the uploaded documents." in q3_res['answer']
    print('SUCCESS: Strict zero-hallucination refusal rule strictly satisfied!')

# Test Page Text Endpoint for View Source
req_page = urllib.request.Request(f"http://127.0.0.1:8000/api/user-docs/{doc_a['doc_id']}/page/1?session_id={session_id}")
with urllib.request.urlopen(req_page) as resp:
    page_res = json.loads(resp.read().decode('utf-8'))
    print('\n=== VIEW SOURCE PAGE ENDPOINT ===')
    print(f"Doc: {page_res['doc_name']}, Page: {page_res['page_number']}")
    print(f"Text preview: {page_res['text'][:120]}...")
    assert len(page_res['text']) > 0

print('\n=============================================')
print('ALL E2E ACCEPTANCE TESTS PASSED SUCCESSFULLY!')
print('=============================================')
