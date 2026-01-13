from pdf2docx import Converter
import os

def convert_pdf_to_docx(pdf_file, docx_file):
    cv = Converter(pdf_file)
    cv.convert(docx_file, start=0, end=None)
    cv.close()

base_dir = r"c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\latex\output"
files = [
    ("检索报告.pdf", "检索报告.docx"),
    ("交底书.pdf", "交底书.docx")
]

for pdf_name, docx_name in files:
    pdf_path = os.path.join(base_dir, pdf_name)
    docx_path = os.path.join(base_dir, docx_name)
    print(f"Converting {pdf_path} to {docx_path}...")
    try:
        convert_pdf_to_docx(pdf_path, docx_path)
        print(f"Successfully converted {pdf_name}")
    except Exception as e:
        print(f"Failed to convert {pdf_name}: {e}")
