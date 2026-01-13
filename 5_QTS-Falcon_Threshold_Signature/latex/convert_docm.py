import zipfile
import os
import shutil

DOCM_PATH = r"c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\temp_template_jiaodishu.docm"
CONVERTED_PATH = r"c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\temp_template_jiaodishu_converted.docx"
EXTRACT_DIR = r"c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\temp_extract"

if os.path.exists(EXTRACT_DIR):
    shutil.rmtree(EXTRACT_DIR)
os.makedirs(EXTRACT_DIR)

print(f"Extracting {DOCM_PATH}...")
with zipfile.ZipFile(DOCM_PATH, 'r') as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)

# Edit [Content_Types].xml
ct_path = os.path.join(EXTRACT_DIR, "[Content_Types].xml")
with open(ct_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the content type
old_type = "application/vnd.ms-word.document.macroEnabled.main+xml"
new_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"

if old_type in content:
    print("Found macro content type, replacing...")
    content = content.replace(old_type, new_type)
    with open(ct_path, 'w', encoding='utf-8') as f:
        f.write(content)
else:
    print("Warning: Macro content type not found in [Content_Types].xml")

# Repackage
print(f"Creating {CONVERTED_PATH}...")
shutil.make_archive(CONVERTED_PATH.replace('.docx', ''), 'zip', EXTRACT_DIR)
shutil.move(CONVERTED_PATH.replace('.docx', '.zip'), CONVERTED_PATH)

# Clean up
shutil.rmtree(EXTRACT_DIR)

# Test opening
from docx import Document
try:
    doc = Document(CONVERTED_PATH)
    print("SUCCESS: Converted and loaded docx.")
    print("--- TABLES ---")
    for i, table in enumerate(doc.tables):
        print(f"Table {i} has {len(table.rows)} rows")
        if len(table.rows) > 0:
             print(f"First row: {[c.text for c in table.rows[0].cells]}")
except Exception as e:
    print(f"ERROR loading converted docx: {e}")
