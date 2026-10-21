from docx import Document

doc = Document('/Users/daxu/PATENTS/10_TITAN_Tensor_Isomorphism_Trapdoor_Signature/模版交底书.docx')
for p in doc.paragraphs:
    if '第三条' in p.text:
        print(repr(p.text))
